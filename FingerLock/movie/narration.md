# Voice-over draft — Infallible Safe movie

A starting point for the stop-action movie's voice-over, one block per scene (the scene videos are `movie/scene_XX_*.mp4`). Say it in your own words. The assignment wants your explanation, so treat these as notes, not a script to read. Each block is about the length of its scene; in iMovie, stretch or trim a scene to fit what you say.

Record on Zoom or QuickTime (File > New Audio Recording), one take per scene if that's easier, then drop the clips under the scene videos.

**01 Title (3 s)**
This is how my safe's neural network turns a camera picture into a number of fingers, and how it knows the hand is mine.

**02 Pixels (8 s)**
The camera looks down at a mat. The safe keeps a grey square of it and shrinks it to 64 by 64: 4,096 numbers, each one how bright that spot is. Before the network sees them, each picture is standardised (minus its average, divided by its spread), so a dim room and a bright room look the same to it.

**03 Convolution (11 s)**
The first layer is a convolution. A filter is just 9 weights in a 3 by 3 square. Put it on one spot of the picture, multiply each of the 9 pixels under it by its weight, add them up, add a bias: that's one number. Slide one pixel right and do it again, all 4,096 times. The result is a feature map: big where the picture matches the filter's pattern. [Say what this filter lights up on in your frames: the edges of the fingers? one side of them?] I never chose its weights; training did.

**04 Eight filters (4 s)**
The first layer has 8 filters, so it makes 8 feature maps. Each one looks for its own small pattern, like an edge at a certain angle, everywhere in the picture at once.

**05 ReLU (3 s)**
Then ReLU, like in my V-fit: negatives become zero, so each map only keeps the places where its pattern was found.

**06 Max pooling (11 s)**
Then max pooling. Take each 2 by 2 block and keep only its biggest number. The map is half as wide and half as tall, but the strong responses survive. That makes everything after it four times cheaper, and it means the hand can move a pixel or two without changing the answer much.

**07 Deeper layers (8 s)**
That's one round. The network does it three times. The second layer's 16 filters each look at all 8 maps at once, so they can combine edges into bigger shapes. The third layer has 32. After three rounds of pooling, the 64 by 64 picture is 32 maps of 8 by 8: 2,048 numbers.

**08 Two answers (8.5 s)**
A fully connected layer squeezes those 2,048 numbers into 64: a description of the hand. From that, two answers. One: seven scores, for no hand and zero to five fingers, and softmax turns them into probabilities. Two: is this my hand? The safe keeps my average description for each count and checks how close this hand is to it.

**09 Training (7 s)**
At the start the filters are random noise. I took about [N] photos of my hand, and a few of friends' hands. Each pass, every wrong answer makes a loss, and backpropagation nudges all [137,544] weights a little downhill, exactly like the gradient descent in my V-fit, just with a lot more weights. You can watch the filters turn into edge detectors as the loss drops.

**10 The safe's rules (9.5 s)**
The network answers about [6] times a second on the UNO Q. I walk up and press the button, and the LEDs light up. The safe only counts a digit when the same answer holds for 0.8 seconds at 80% or more, and I take my hand off the mat between digits. After three digits it checks two things: the code, and whether the hand looked like mine on average across the whole code. The right code from my hand opens it; three refused codes in a row and it locks itself for ten seconds. And if someone forces me to open it, there's a duress code: it opens exactly the same way, but it secretly sends my phone an alert with a photo.

**11 End (3 s)**
One network, two answers: how many fingers, and whose hand.

---
Fill in the bracketed numbers from `figures/results.json` and `figures/bench.json` after training and the speed tests.
