"""Record a short audio clip, turn it into a spectrogram, and label the notes.

Records 5 seconds from the default microphone (or reads a .wav with --file),
computes a short-time Fourier transform, picks the strongest spectral peaks
in each frame, throws away peaks that are just harmonics (overtones) of a
lower note, snaps what's left to the nearest equal-tempered note name
(A4 = 440 Hz), and groups consecutive frames into note events. The events
are drawn on top of the spectrogram and printed as a table.

    python spectrogram_notes.py                  # record 5 s from the mic
    python spectrogram_notes.py --duration 8     # record longer
    python spectrogram_notes.py --file clip.wav  # analyze an existing file
    python spectrogram_notes.py --save           # also keep the .wav + .png
"""

import argparse
import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks

SAMPLE_RATE = 44100
DURATION = 5.0          # seconds to record

N_FFT = 8192            # window length -> ~5.4 Hz per bin at 44.1 kHz
HOP = 1024              # ~23 ms between frames
F_MIN = 75.0            # Hz, just below low E on a guitar (82 Hz)
F_MAX = 4200.0          # Hz, just above C8 (4186 Hz)

THRESHOLD_DB = 35.0     # peaks must be within this many dB of the loudest point in the clip
FRAME_RANGE_DB = 25.0   # ...and within this many dB of the loudest peak in their own frame
PROMINENCE_DB = 10.0    # how far a peak has to stick up above its neighbors
HARMONIC_TOL = 0.03     # 3% (~50 cents) counts as "an integer multiple"
MAX_HARMONIC = 8

MIN_NOTE_SEC = 0.10     # drop events shorter than this
MAX_GAP_FRAMES = 2      # bridge dropouts this short inside one note

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- audio in

def record(duration, sample_rate, device=None):
    import sounddevice as sd   # only needed when recording, not for --file

    print(f"Recording {duration:g} s... play something!")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                   channels=1, dtype="float32", device=device)
    sd.wait()
    print("Done.")
    return audio[:, 0], sample_rate


def load_wav(path):
    sample_rate, audio = wavfile.read(path)
    if np.issubdtype(audio.dtype, np.integer):
        audio = audio / np.iinfo(audio.dtype).max
    audio = audio.astype(np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # stereo -> mono
    return audio, sample_rate


# ------------------------------------------------------------- spectrogram

def spectrogram(audio, sample_rate, n_fft=N_FFT, hop=HOP):
    """Return (times, freqs, magnitude in dB) with frames centered on times."""
    padded = np.pad(audio, n_fft // 2)
    n_frames = 1 + (len(padded) - n_fft) // hop
    frames = np.lib.stride_tricks.sliding_window_view(padded, n_fft)[::hop][:n_frames]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(n_fft), axis=1))
    mag_db = 20 * np.log10(spectrum + 1e-10)
    times = np.arange(n_frames) * hop / sample_rate
    freqs = np.fft.rfftfreq(n_fft, 1 / sample_rate)
    return times, freqs, mag_db


# ------------------------------------------------------------ note helpers

def freq_to_midi(freq):
    return 69 + 12 * np.log2(freq / 440.0)


def midi_to_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def note_name(midi):
    midi = int(round(midi))
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def refine_peak(frame_db, i, bin_hz):
    """Parabolic interpolation around bin i -> sub-bin frequency estimate."""
    a, b, c = frame_db[i - 1], frame_db[i], frame_db[i + 1]
    denom = a - 2 * b + c
    offset = 0.5 * (a - c) / denom if denom != 0 else 0.0
    return (i + offset) * bin_hz


def is_harmonic(freq, fundamentals):
    for f0 in fundamentals:
        k = round(freq / f0)
        if 2 <= k <= MAX_HARMONIC and abs(freq / (k * f0) - 1) < HARMONIC_TOL:
            return True
    return False


# --------------------------------------------------------- classification

def detect_frame_notes(freqs, mag_db):
    """For each frame, return a list of (midi, freq, dB) for the notes found."""
    bin_hz = freqs[1]
    lo = np.searchsorted(freqs, F_MIN)
    hi = np.searchsorted(freqs, F_MAX)
    clip_floor = mag_db[:, lo:hi].max() - THRESHOLD_DB

    per_frame = []
    for frame_db in mag_db:
        band = frame_db[lo:hi]
        height = max(clip_floor, band.max() - FRAME_RANGE_DB)
        peaks, _ = find_peaks(band, height=height, prominence=PROMINENCE_DB)

        # Walk peaks from low to high: a peak sitting at 2x, 3x, ... of a
        # note we already accepted is that note's overtone, not a new note.
        fundamentals, notes = [], []
        for p in peaks + lo:
            freq = refine_peak(frame_db, p, bin_hz)
            if is_harmonic(freq, fundamentals):
                continue
            fundamentals.append(freq)
            notes.append((int(round(freq_to_midi(freq))), freq, frame_db[p]))
        per_frame.append(notes)
    return per_frame


def group_events(times, per_frame):
    """Join consecutive frames holding the same note into note events."""
    hop_sec = times[1] - times[0]
    active = {}   # midi -> dict for the event currently being built
    events = []

    def close(midi):
        ev = active.pop(midi)
        duration = ev["last"] - ev["first"] + 1
        if duration * hop_sec >= MIN_NOTE_SEC:
            freq = float(np.median(ev["freqs"]))
            events.append({
                "note": note_name(midi),
                "midi": midi,
                "start": max(0.0, times[ev["first"]] - hop_sec / 2),
                "end": times[ev["last"]] + hop_sec / 2,
                "freq": freq,
                "cents": 100 * (freq_to_midi(freq) - midi),
                "db": max(ev["dbs"]),
            })

    for i, notes in enumerate(per_frame):
        for midi, freq, db in notes:
            ev = active.setdefault(midi, {"first": i, "last": i, "freqs": [], "dbs": []})
            ev["last"] = i
            ev["freqs"].append(freq)
            ev["dbs"].append(db)
        for midi in [m for m, ev in active.items() if i - ev["last"] > MAX_GAP_FRAMES]:
            close(midi)
    for midi in list(active):
        close(midi)

    return sorted(events, key=lambda e: (e["start"], e["midi"]))


# ------------------------------------------------------------------ output

def print_events(events):
    if not events:
        print("\nNo notes detected. Try playing louder or closer to the mic, "
              "or raise --threshold to count quieter peaks.")
        return
    print(f"\n{'note':>5} {'start':>7} {'end':>7} {'freq (Hz)':>10} {'cents':>6}")
    for e in events:
        print(f"{e['note']:>5} {e['start']:7.2f} {e['end']:7.2f} "
              f"{e['freq']:10.1f} {e['cents']:+6.0f}")
    distinct = sorted({e["midi"] for e in events})
    print("\nNotes present:", ", ".join(note_name(m) for m in distinct))


def plot(times, freqs, mag_db, events, title):
    lo = np.searchsorted(freqs, F_MIN)
    hi = np.searchsorted(freqs, F_MAX)
    shown = mag_db[:, lo:hi].T
    vmax = shown.max()

    fig, ax = plt.subplots(figsize=(12, 6.5))
    mesh = ax.pcolormesh(times, freqs[lo:hi], shown, shading="auto",
                         cmap="magma", vmin=vmax - 80, vmax=vmax)
    ax.set_yscale("log")
    ax.set_ylim(F_MIN, F_MAX)

    # Label the y-axis with every C so frequencies read as octaves.
    c_midis = [m for m in range(24, 121, 12) if F_MIN <= midi_to_freq(m) <= F_MAX]
    ax.set_yticks([midi_to_freq(m) for m in c_midis])
    ax.set_yticklabels([f"{note_name(m)}\n{midi_to_freq(m):.0f} Hz" for m in c_midis])
    ax.minorticks_off()

    for e in events:
        ax.hlines(e["freq"], e["start"], e["end"], colors="cyan", linewidth=2)
        ax.text(e["start"], e["freq"] * 1.04, e["note"], color="white",
                fontsize=9, fontweight="bold", va="bottom",
                bbox=dict(facecolor="black", alpha=0.55, pad=1.5, edgecolor="none"))

    distinct = sorted({e["midi"] for e in events})
    notes_str = ", ".join(note_name(m) for m in distinct) or "none"
    ax.set_title(f"{title}\nNotes present: {notes_str}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (log scale)")
    fig.colorbar(mesh, ax=ax, label="Magnitude (dB)")
    fig.tight_layout()
    return fig


# -------------------------------------------------------------------- main

def main():
    global THRESHOLD_DB
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--duration", type=float, default=DURATION,
                        help=f"seconds to record (default {DURATION:g})")
    parser.add_argument("--file", type=Path, help="analyze this .wav instead of recording")
    parser.add_argument("--device", help="input device name or index (see `python -m sounddevice`)")
    parser.add_argument("--threshold", type=float, default=THRESHOLD_DB,
                        help=f"dB below the clip's loudest point to still count a peak "
                             f"(default {THRESHOLD_DB:g}; raise to catch quieter notes)")
    parser.add_argument("--save", action="store_true",
                        help="save the recording (.wav) and spectrogram (.png) to recordings/")
    parser.add_argument("--no-show", action="store_true", help="don't open the plot window")
    args = parser.parse_args()
    THRESHOLD_DB = args.threshold

    if args.file:
        audio, sample_rate = load_wav(args.file)
        title = args.file.name
    else:
        device = int(args.device) if args.device and args.device.isdigit() else args.device
        audio, sample_rate = record(args.duration, SAMPLE_RATE, device)
        title = f"Recording {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"

    times, freqs, mag_db = spectrogram(audio, sample_rate)
    events = group_events(times, detect_frame_notes(freqs, mag_db))
    print_events(events)
    fig = plot(times, freqs, mag_db, events, title)

    if args.save:
        out_dir = HERE / "recordings"
        out_dir.mkdir(exist_ok=True)
        stem = args.file.stem if args.file else f"clip_{datetime.datetime.now():%Y%m%d_%H%M%S}"
        if not args.file:
            wavfile.write(out_dir / f"{stem}.wav", sample_rate, audio)
        fig.savefig(out_dir / f"{stem}_spectrogram.png", dpi=150)
        print(f"\nSaved to {out_dir}/{stem}*")

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
