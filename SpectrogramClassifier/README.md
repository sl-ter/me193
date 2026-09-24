# Spectrogram classifier — 9/24

Records a 5-second audio clip from the mic, turns it into a spectrogram, and
works out which musical notes are in it. Each detected note is labeled on
the spectrogram (a cyan line over the note's duration and its name, e.g.
`A4`), and a table of notes with start/end times, frequency, and how many
cents sharp or flat each one is gets printed to the terminal.

## Files

- `spectrogram_notes.py` — the whole thing: record → spectrogram → note
  detection → labeled plot. Everything it needs is in this one file.

Dependencies: `sounddevice` (mic recording; its macOS wheel ships its own
PortAudio, so no `brew install` needed), plus `numpy`, `scipy`, and
`matplotlib`, which were already in the root `requirements.txt`. It uses the
shared root venv, not a venv of its own.

## Run it

```bash
cd ~/Code/Projects/me193
source venv/bin/activate
python SpectrogramClassifier/spectrogram_notes.py                   # record 5 s and analyze it
python SpectrogramClassifier/spectrogram_notes.py --duration 8      # record for longer
python SpectrogramClassifier/spectrogram_notes.py --file clip.wav   # analyze an existing .wav
python SpectrogramClassifier/spectrogram_notes.py --save            # also keep the .wav + .png
python SpectrogramClassifier/spectrogram_notes.py --threshold 45    # count quieter notes
python -m sounddevice                                               # list mics, then pass --device N
```

### Options

| Option | Default | What it does |
|---|---|---|
| `--duration SECONDS` | `5` | How long to record. |
| `--file PATH` | — | Analyze an existing `.wav` instead of recording. Stereo is mixed to mono; any sample rate works. |
| `--device N_OR_NAME` | system default mic | Input device index or name. Run `python -m sounddevice` to list them. |
| `--threshold DB` | `35` | How many dB below the clip's loudest point a peak can be and still count as a note. Raise it to catch quieter notes; lower it if background noise shows up as notes. |
| `--save` | off | Save the recording (`.wav`) and the labeled spectrogram (`.png`) to `recordings/`. With `--file`, only the `.png` is saved. |
| `--no-show` | off | Don't open the plot window. Useful with `--save`. |
| `-h`, `--help` | — | Print the option list. |

Other tuning knobs (window size, frequency range, minimum note length,
overtone tolerance) are constants at the top of `spectrogram_notes.py`.

`--save` writes to `SpectrogramClassifier/recordings/`, which is gitignored.
Without `--save`, nothing is written to disk. You can still save the image
from the plot window's save button.

Run it from Terminal.app or iTerm2, not kitty: kitty doesn't reliably pass
macOS mic/camera permission through to child processes (see the
`PoseRaceCar` note in the session log). On the first run macOS asks for
microphone access.

## How it classifies notes

1. **Spectrogram:** Hann-windowed FFT, 8192 samples per window (~5.4 Hz
   per bin), hopping 1024 samples (~23 ms). The big window is what lets it
   tell apart low notes that are only a few Hz apart.
2. **Peaks per frame:** in each time slice, it finds spectral peaks
   between 75 Hz and 4200 Hz that are loud enough (within `--threshold` dB
   of the loudest point in the clip, and within 25 dB of the loudest peak in
   that slice) and stick up at least 10 dB above their neighbors. Parabolic
   interpolation refines each peak's frequency below one bin.
3. **Drop overtones:** a real note also shows up at 2×, 3×, 4×… its
   frequency (the stacked lines in the plot). Walking from low to high, any
   peak within ~3% of an integer multiple of a note already found counts as
   an overtone and is dropped.
4. **Name it:** `midi = 69 + 12·log2(f / 440)`, rounded to the nearest
   semitone → note name + octave. The leftover fraction is the cents offset.
5. **Group into events:** consecutive frames holding the same note merge
   into one event. Dropouts of up to 2 frames are bridged, and events
   shorter than 0.1 s are discarded.

Tested on a synthesized clip with overtones and noise (C4, E4, G4, then a
C-major chord, then an A2 detuned 17 cents sharp): it found all of them,
labeled the three chord notes separately, and read the A2 as +16 cents.

## Known limitations

- **Octaves in a chord get merged.** If C4 and C5 sound together, C5 sits
  exactly on C4's 2nd harmonic, so it's treated as an overtone.
- **Weak fundamentals.** Some sounds (low piano notes, some voices) have
  a fundamental quieter than their overtones. If it drops below the
  threshold, the note can be reported an octave or more too high.
- **Below ~75 Hz is ignored.** This keeps out 60 Hz mains hum and its
  harmonics, but it also skips the lowest bass notes. Change `F_MIN` if
  you need them.
- Noisy rooms add spurious short notes. Play close to the mic.
