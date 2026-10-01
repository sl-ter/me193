// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

// Generic LED matrix frame receiver: all the display logic (metrics,
// formatting, scrolling) lives in python/main.py. This sketch just keeps
// redrawing whatever frame Python last pushed over the Bridge, same pattern
// as the core "LED Matrix Frame" example.

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>

Arduino_LED_Matrix matrix;

const uint8_t FRAME_ROWS = 8;
const uint8_t FRAME_COLS = 13;
const uint8_t FRAME_SIZE = FRAME_ROWS * FRAME_COLS;

uint8_t frame[FRAME_SIZE] = {0};

void draw(std::vector<uint8_t> newFrame) {
  size_t len = min(newFrame.size(), (size_t)FRAME_SIZE);
  memcpy(frame, newFrame.data(), len);
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);  // brightness values 0-7, matches Frame()
  matrix.clear();

  Bridge.begin();
  Bridge.provide("draw", draw);
}

void loop() {
  matrix.draw(frame);
  delay(10);
}
