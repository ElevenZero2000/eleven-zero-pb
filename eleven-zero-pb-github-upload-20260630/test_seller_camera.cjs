const assert = require('node:assert/strict');
const test = require('node:test');
const { File } = require('node:buffer');
const { create } = require('./seller-camera.js');

class Element {
  constructor() { this.handlers = new Map(); this.attributes = {}; this.textContent = ''; this.disabled = false; }
  addEventListener(name, fn) { if (!this.handlers.has(name)) this.handlers.set(name, new Set()); this.handlers.get(name).add(fn); }
  removeEventListener(name, fn) { this.handlers.get(name)?.delete(fn); }
  dispatch(name, values = {}) { const event = { preventDefault() { this.prevented = true; }, ...values }; this.handlers.get(name)?.forEach(fn => fn(event)); return event; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  focus() { this.focused = true; }
}

function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }

function setup(overrides = {}) {
  const doc = new Element(), win = new Element(), dialog = new Element(), video = new Element();
  const status = new Element(), captureButton = new Element(), closeButton = new Element(), uploadButton = new Element();
  captureButton.textContent = 'Take photo';
  doc.activeElement = new Element();
  doc.hidden = false;
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.dispatch('close'); };
  video.videoWidth = 3840; video.videoHeight = 2160; video.readyState = 4;
  video.play = async () => {};
  video.pause = () => {};
  const tracks = [0, 1].map(() => Object.assign(new Element(), { stopped: 0, stop() { this.stopped += 1; } }));
  const stream = { getTracks: () => tracks };
  const canvas = { width: 0, height: 0, getContext: () => ({ drawImage(...args) { canvas.drawn = args; } }), toBlob(fn, type, quality) { canvas.type = type; canvas.quality = quality; fn(new Blob(['test-photo'], { type })); } };
  const calls = [], photos = [], uploads = [], fallbacks = [];
  const mediaDevices = { async getUserMedia(constraints) { calls.push(constraints); return stream; } };
  let remaining = 4;
  const options = { dialog, video, status, captureButton, closeButton, uploadButton,
    getRemaining: () => remaining,
    async onPhoto(file) { photos.push(file); remaining -= 1; },
    onUpload: () => uploads.push(true),
    ...overrides.options,
  };
  const environment = { document: doc, window: win, mediaDevices, File, isSecureContext: true, now: () => 123, createCanvas: () => canvas, ...overrides.environment };
  const camera = create(options, environment);
  return { camera, doc, win, dialog, video, status, captureButton, closeButton, uploadButton, tracks, stream, canvas, calls, photos, uploads, fallbacks, setRemaining(value) { remaining = value; } };
}

test('does not ask for camera permission until explicitly opened; never asks for audio', async () => {
  const f = setup();
  assert.equal(f.calls.length, 0);
  assert.equal(f.captureButton.disabled, true);
  assert.equal(await f.camera.open(), true);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].audio, false);
  assert.equal(f.calls[0].video.facingMode.ideal, 'environment');
  assert.equal(f.video.playsInline, true);
  assert.equal(f.video.muted, true);
  assert.equal(f.captureButton.disabled, false);
});

test('captures a JPEG File using the existing upload callback, preserving proportions', async () => {
  const f = setup(); await f.camera.open();
  assert.equal(await f.camera.capture(), true);
  assert.equal(f.photos.length, 1);
  assert.equal(f.photos[0].type, 'image/jpeg');
  assert.equal(f.photos[0].name, 'paddle-photo-123.jpg');
  assert.equal(f.canvas.width, 2048);
  assert.equal(f.canvas.height, 1152);
  assert.equal(f.canvas.drawn[0], f.video);
  assert.equal(f.camera.isOpen(), true);
  assert.match(f.status.textContent, /Photo added/);
});

test('waits for a real video frame before enabling capture', async () => {
  const f = setup(); f.video.videoWidth = 0; f.video.readyState = 1; await f.camera.open();
  assert.equal(f.captureButton.disabled, true);
  assert.equal(await f.camera.capture(), false);
  f.video.videoWidth = 1920; f.video.readyState = 2; f.video.dispatch('loadeddata');
  assert.equal(f.captureButton.disabled, false);
});

test('serializes captures while a photo is being added', async () => {
  const pending = deferred();
  const f = setup({ options: { onPhoto: () => pending.promise } }); await f.camera.open();
  const first = f.camera.capture(); await Promise.resolve();
  assert.equal(f.captureButton.disabled, true);
  assert.equal(f.uploadButton.disabled, true);
  assert.equal(await f.camera.capture(), false);
  pending.resolve(true); assert.equal(await first, true);
  assert.equal(f.captureButton.disabled, false);
  assert.equal(f.uploadButton.disabled, false);
});

test('closes and stops every track when the fourth photo is added', async () => {
  const f = setup(); await f.camera.open();
  for (let i = 0; i < 4; i += 1) assert.equal(await f.camera.capture(), true);
  assert.equal(f.photos.length, 4);
  assert.equal(f.camera.isOpen(), false);
  assert.ok(f.tracks.every(track => track.stopped === 1));
  assert.equal(f.video.srcObject, null);
  assert.equal(await f.camera.open(), false);
  assert.equal(f.calls.length, 1);
});

test('cancel preserves photos already added and stops the preview', async () => {
  const f = setup(); await f.camera.open(); await f.camera.capture();
  f.closeButton.dispatch('click');
  assert.equal(f.photos.length, 1);
  assert.equal(f.video.srcObject, null);
  assert.ok(f.tracks.every(track => track.stopped === 1));
  assert.equal(f.doc.activeElement.focused, true);
});

for (const exit of ['escape', 'cancel', 'pagehide', 'hidden', 'dialog-close']) {
  test(`${exit} stops the camera and closes it`, async () => {
    const f = setup(); await f.camera.open();
    if (exit === 'escape') f.doc.dispatch('keydown', { key: 'Escape' });
    if (exit === 'cancel') f.dialog.dispatch('cancel');
    if (exit === 'pagehide') f.win.dispatch('pagehide');
    if (exit === 'hidden') { f.doc.hidden = true; f.doc.dispatch('visibilitychange'); }
    if (exit === 'dialog-close') f.dialog.close();
    assert.equal(f.camera.isOpen(), false);
    assert.ok(f.tracks.every(track => track.stopped === 1));
  });
}

test('closing while permission is pending stops the late-arriving stream', async () => {
  const pending = deferred();
  const f = setup({ environment: { mediaDevices: { getUserMedia: () => pending.promise } } });
  const opening = f.camera.open(); f.camera.close(); pending.resolve(f.stream);
  assert.equal(await opening, false);
  assert.ok(f.tracks.every(track => track.stopped === 1));
  assert.equal(f.video.srcObject, null);
});

test('an old permission result cannot replace a newly opened camera', async () => {
  const first = deferred(), second = deferred(); let count = 0;
  const f = setup({ environment: { mediaDevices: { getUserMedia: () => (++count === 1 ? first.promise : second.promise) } } });
  const old = f.camera.open(); f.camera.close(); const current = f.camera.open();
  const oldTrack = { stopped: false, stop() { this.stopped = true; } };
  second.resolve(f.stream); await current;
  first.resolve({ getTracks: () => [oldTrack] }); await old;
  assert.equal(oldTrack.stopped, true);
  assert.equal(f.video.srcObject, f.stream);
  assert.ok(f.tracks.every(track => track.stopped === 0));
});

test('closing during JPEG encoding does not add a surprise photo', async () => {
  const f = setup(); let complete;
  f.canvas.toBlob = fn => { complete = fn; };
  await f.camera.open(); const capture = f.camera.capture(); f.camera.close();
  complete(new Blob(['image'], { type: 'image/jpeg' })); await capture;
  assert.equal(f.photos.length, 0);
});

test('upload fallback stops the camera before opening the file chooser', async () => {
  const f = setup(); await f.camera.open(); f.uploadButton.dispatch('click');
  assert.equal(f.uploads.length, 1);
  assert.equal(f.camera.isOpen(), false);
  assert.ok(f.tracks.every(track => track.stopped === 1));
});

for (const [name, message] of [['NotAllowedError', /blocked/], ['NotFoundError', /No camera/], ['NotReadableError', /in use/], ['UnknownError', /could not start/]]) {
  test(`shows friendly ${name} errors without losing the upload fallback`, async () => {
    const f = setup({ environment: { mediaDevices: { getUserMedia: async () => { const error = new Error('private device detail'); error.name = name; throw error; } } } });
    assert.equal(await f.camera.open(), false);
    assert.match(f.status.textContent, message);
    assert.doesNotMatch(f.status.textContent, /private device detail/);
    assert.equal(f.captureButton.disabled, true);
    assert.equal(f.uploadButton.disabled, false);
  });
}

test('unsupported/insecure camera invokes the optional native capture fallback without permissions', async () => {
  const messages = [];
  const f = setup({ options: { onFallback: message => messages.push(message) }, environment: { isSecureContext: false } });
  assert.equal(await f.camera.open(), false);
  assert.equal(messages.length, 1);
  assert.equal(f.calls.length, 0);
  assert.equal(f.camera.isOpen(), false);
});

test('failed capture is retryable and never clears existing pictures', async () => {
  const f = setup(); await f.camera.open(); await f.camera.capture();
  f.canvas.toBlob = fn => fn(null);
  assert.equal(await f.camera.capture(), false);
  assert.equal(f.photos.length, 1);
  assert.match(f.status.textContent, /could not be added/);
  assert.equal(f.captureButton.disabled, false);
});

test('pipeline rejection keeps capture retryable without claiming success', async () => {
  const f = setup({ options: { onPhoto: async () => false } }); await f.camera.open();
  assert.equal(await f.camera.capture(), false);
  assert.match(f.status.textContent, /not added/);
  assert.equal(f.captureButton.disabled, false);
});

test('destroy removes listeners and prevents reopening', async () => {
  const f = setup(); await f.camera.open(); f.camera.destroy();
  assert.equal(await f.camera.open(), false);
  assert.ok(f.tracks.every(track => track.stopped === 1));
  assert.equal(f.doc.handlers.get('visibilitychange').size, 0);
  assert.equal(f.win.handlers.get('pagehide').size, 0);
});

test('preview playback failure releases every camera track', async () => {
  const f = setup();
  f.video.play = async () => { throw new Error('Playback unavailable'); };
  assert.equal(await f.camera.open(), false);
  assert.ok(f.tracks.every(track => track.stopped === 1));
  assert.equal(f.video.srcObject, null);
  assert.match(f.status.textContent, /could not start/);
  assert.equal(f.uploadButton.disabled, false);
});

test('camera hardware ending stops preview and keeps the upload fallback available', async () => {
  const f = setup(); await f.camera.open();
  f.tracks[0].dispatch('ended');
  assert.ok(f.tracks.every(track => track.stopped === 1));
  assert.equal(f.video.srcObject, null);
  assert.equal(f.captureButton.disabled, true);
  assert.equal(f.uploadButton.disabled, false);
  assert.match(f.status.textContent, /camera stopped/);
  assert.ok(f.tracks.every(track => track.handlers.get('ended').size === 0));
});
