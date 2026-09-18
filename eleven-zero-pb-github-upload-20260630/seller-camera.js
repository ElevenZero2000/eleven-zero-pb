(function (root) {
  "use strict";

  function cameraError(error) {
    if (error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError") {
      return "Camera access was blocked. Allow it in your browser settings, or upload a photo.";
    }
    if (error?.name === "NotFoundError" || error?.name === "DevicesNotFoundError") {
      return "No camera found. You can still upload a photo.";
    }
    if (error?.name === "NotReadableError" || error?.name === "TrackStartError") {
      return "Your camera may be in use by another app. Close that app and try again, or upload a photo.";
    }
    return "The camera could not start. Please try again, or upload a photo.";
  }

  // No permission is requested until open() is called by the seller's button.
  // The second argument is only a test seam: production uses browser APIs.
  function create(options, environment = {}) {
    const { dialog, video, status, captureButton, closeButton, uploadButton } = options;
    const doc = environment.document || root.document;
    const win = environment.window || root;
    const mediaDevices = environment.mediaDevices || root.navigator?.mediaDevices;
    const createCanvas = environment.createCanvas || (() => doc.createElement("canvas"));
    const FileType = environment.File || root.File;
    const now = environment.now || Date.now;
    const secure = environment.isSecureContext ?? root.isSecureContext;
    let opened = false;
    let destroyed = false;
    let generation = 0;
    let stream = null;
    let streamListeners = [];
    let saving = false;
    let opener = null;
    const captureLabel = captureButton.textContent || "Take photo";
    const listeners = [];

    function listen(element, type, callback) {
      element?.addEventListener(type, callback);
      listeners.push(() => element?.removeEventListener(type, callback));
    }

    function remaining() {
      const value = Number(options.getRemaining?.() ?? 4);
      return Number.isFinite(value) ? Math.max(0, value) : 0;
    }

    function say(message) {
      status.textContent = message;
    }

    function stopTracks(value) {
      value?.getTracks().forEach((track) => {
        try { track.stop(); } catch { /* One failed track must not leave others on. */ }
      });
    }

    function stopCamera() {
      streamListeners.forEach((remove) => remove());
      streamListeners = [];
      stopTracks(stream);
      stream = null;
      try { video.pause(); } catch { /* A pending preview may not have started. */ }
      video.srcObject = null;
    }

    function updateControls() {
      captureButton.disabled = !opened || !stream || saving || remaining() < 1
        || !video.videoWidth || !video.videoHeight || video.readyState < 2;
      captureButton.textContent = saving ? "Adding photo…" : captureLabel;
      captureButton.setAttribute("aria-busy", String(saving));
      if (uploadButton) uploadButton.disabled = saving;
    }

    function close() {
      const wasOpen = opened;
      opened = false;
      generation += 1;
      stopCamera();
      updateControls();
      if (dialog.open && typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
      if (wasOpen && opener?.isConnected !== false && !doc.hidden) opener?.focus?.();
      opener = null;
    }

    async function open() {
      if (destroyed || opened || saving) return false;
      if (remaining() < 1) return false;
      opened = true;
      const current = ++generation;
      opener = doc.activeElement;
      video.muted = true;
      video.autoplay = true;
      video.playsInline = true;
      video.setAttribute("playsinline", "");
      video.setAttribute("muted", "");
      say("Opening camera…");
      updateControls();
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");

      if (secure === false || !mediaDevices?.getUserMedia) {
        const message = "This browser cannot open the camera here. You can still upload a photo.";
        say(message);
        if (typeof options.onFallback === "function") {
          close();
          options.onFallback(message);
        }
        return false;
      }

      try {
        const candidate = await mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1920 },
            height: { ideal: 1440 },
          },
        });
        if (!opened || current !== generation || doc.hidden) {
          stopTracks(candidate);
          return false;
        }
        stream = candidate;
        candidate.getTracks().forEach((track) => {
          const ended = () => {
            if (!opened || current !== generation || stream !== candidate) return;
            stopCamera();
            say("The camera stopped. Close this window and try again, or upload a photo.");
            updateControls();
          };
          track.addEventListener?.("ended", ended);
          streamListeners.push(() => track.removeEventListener?.("ended", ended));
        });
        video.srcObject = candidate;
        await video.play();
        if (!opened || current !== generation || stream !== candidate) return false;
        say("Frame your paddle, then take a photo.");
        updateControls();
        return true;
      } catch (error) {
        if (!opened || current !== generation) return false;
        stopCamera();
        say(cameraError(error));
        updateControls();
        return false;
      }
    }

    async function capture() {
      if (!opened || !stream || saving || captureButton.disabled) return false;
      if (remaining() < 1) {
        close();
        return false;
      }
      const current = generation;
      saving = true;
      say("Adding photo…");
      updateControls();
      try {
        const canvas = createCanvas();
        // Preserve the frame's proportions while avoiding oversized uploads.
        const scale = Math.min(1, 2048 / Math.max(video.videoWidth, video.videoHeight));
        canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
        canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Camera image unavailable");
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise((resolve, reject) => {
          canvas.toBlob((value) => value ? resolve(value) : reject(new Error("Camera image unavailable")), "image/jpeg", 0.9);
        });
        // Closing a pending capture must not add a surprise photo afterward.
        if (!opened || current !== generation) return false;
        const file = new FileType([blob], `paddle-photo-${now()}.jpg`, { type: "image/jpeg" });
        const added = await options.onPhoto(file);
        if (!opened || current !== generation) return added !== false;
        if (added === false) {
          say("The photo was not added. Try again, or upload a photo.");
          return false;
        }
        if (remaining() < 1) close();
        else say(`Photo added. ${remaining()} photo${remaining() === 1 ? "" : "s"} left.`);
        return true;
      } catch {
        if (opened && current === generation) {
          say("The photo could not be added. Try again, or upload a photo.");
        }
        return false;
      } finally {
        saving = false;
        updateControls();
      }
    }

    listen(captureButton, "click", () => { void capture(); });
    listen(closeButton, "click", close);
    listen(uploadButton, "click", () => {
      if (saving) return;
      close();
      options.onUpload?.();
    });
    listen(dialog, "cancel", (event) => { event.preventDefault(); close(); });
    listen(dialog, "close", () => { if (opened && !dialog.open) close(); });
    listen(doc, "keydown", (event) => {
      if (opened && event.key === "Escape") { event.preventDefault(); close(); }
    });
    listen(win, "pagehide", close);
    listen(doc, "visibilitychange", () => { if (doc.hidden) close(); });
    ["loadedmetadata", "loadeddata", "canplay"].forEach((name) => listen(video, name, updateControls));
    updateControls();

    return {
      open,
      close,
      capture,
      isOpen: () => opened,
      destroy() {
        destroyed = true;
        close();
        listeners.forEach((remove) => remove());
      },
    };
  }

  const api = { create };
  root.ElevenZeroSellerCamera = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
