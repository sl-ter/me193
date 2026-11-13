# Voice-over: The Infallible Safe movie

The script for the stop-action movie, one block per scene, to read out loud over `movie/infallible_safe.mp4`. Make it sound like you: change any words you want. `render.py` times each scene to its block (150 words a minute, plus a one-second breath), so after changing the words, render again (`python FingerLock/movie/render.py`) and the scenes follow. It prints when each scene starts; update the times in the headings below to match.

## How to record

The simplest way is one take over the whole movie:

1. Open `FingerLock/movie/infallible_safe.mp4` in QuickTime. Start a recording in a second window: File > New Audio Recording (or record yourself on Zoom).
2. Press play on the movie and read each block when its scene starts (the times are in the headings). If you fall a little behind, skip a breath at the next scene change.
3. Trim the silence before you pressed play (QuickTime: Edit > Trim), save the audio, say as `~/Desktop/voiceover.m4a`, and put it under the movie:

```
cd ~/Code/Projects/me193
ffmpeg -i FingerLock/movie/infallible_safe.mp4 -i ~/Desktop/voiceover.m4a -map 0:v -map 1:a -c:v copy -c:a aac FingerLock/movie/infallible_safe_voiced.mp4
```

If one take feels rushed, use iMovie instead: drop in the scene videos (`movie/scene_01_title.mp4` to `scene_11_end.mp4`) in order, record each block over its clip with Window > Record Voiceover, and stretch or trim each clip to fit.

Keep the recording out of the repo folder (the Desktop is fine): the movie folder only ignores videos and frames.

## 01 Title (starts 0:00)
Here's how my safe's neural network counts fingers. Every filter and feature map on screen comes from the real trained network.

## 02 What the camera sees (starts 0:09)
It starts with the webcam looking down at the mat. The safe takes a grey square of the picture and shrinks it to 64 by 64: 4,096 numbers, one for how bright each spot is.

## 03 Convolution (starts 0:26)
The first layer is a convolution. A filter is a 3 by 3 grid of weights. It sits on one spot, multiplies the 9 pixels under it by its 9 weights, adds them up, and adds a bias: one number in the feature map. Then it slides one pixel over and does it again, all 4,096 times. This filter lights up along the right edge of each finger. Training picked its weights, not me.

## 04 Eight filters (starts 0:58)
Layer one has 8 filters, so it makes 8 maps. Some find edges at different angles. Others light up on the whole hand, or on the mat.

## 05 ReLU (starts 1:10)
Then ReLU, same as my V-fit: every negative becomes zero, so each map only keeps the spots where its pattern showed up.

## 06 Max pooling (starts 1:20)
Then max pooling: each 2 by 2 block keeps only its biggest number. That halves the width and the height, so there's a quarter as much to compute, but the strongest responses survive.

## 07 Deeper layers (starts 1:34)
That's one round, and the network does three. Layer two's 16 filters each look at all 8 maps at once, so they can combine edges into bigger shapes. Layer three has 32. After three rounds, my photo is 32 maps of 8 by 8: 2,048 numbers.

## 08 Fully connected and softmax (starts 1:56)
A fully connected layer squeezes those 2,048 numbers down to 64, kind of a description of the hand. A last layer turns those into 7 scores: no hand, or zero to five fingers. Softmax turns the scores into probabilities that add up to one. Here: three fingers, at 99.7 percent.

## 09 Training (starts 2:19)
So where do the weights come from? Training. I took 8,576 photos, a little over half of them my hand and the rest Subject 1's and Subject 2's. Every pass, each one comes back randomly spun, shifted, flipped, brighter or darker, so the network can't just memorize pixels. The filters start as random noise. The loss is cross-entropy, since it's picking a category. Backpropagation finds which way to nudge every weight to lower it, and gradient descent takes a small step downhill. Same idea as my V-fit, just with 137,544 weights.

## 10 The safe's rules (starts 3:00)
On the UNO Q, all of that runs about 15 times a second. But the network only says what it sees; the rules decide. The safe sleeps until I press the button. A digit counts once the network is at least 70 percent sure of the same answer for 0.8 seconds, then my hand leaves the mat. The right three digits open the latch. A wrong code gets an X, and three in a row lock it for 10 seconds and send an alert with a photo. My duress code opens it exactly the same way, but quietly sends my phone an alert.

## 11 End (starts 3:44)
137,544 weights, trained from scratch, counting my fingers on a little Arduino.
