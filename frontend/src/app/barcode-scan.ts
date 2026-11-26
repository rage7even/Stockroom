import { afterNextRender, Component, ElementRef, inject, Injector, OnDestroy, input, output, signal, viewChild } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { readBarcodeRow } from "./code128";
import { Icon } from "./icon";
import { Modal } from "./modal";
import { Language } from "./language";

export interface ScanResult {
  barcode: string;
  source: "camera" | "manual";
}

type Detector = { detect(video: HTMLVideoElement): Promise<{ rawValue: string }[]> };
type DetectorConstructor = new (options: { formats: string[] }) => Detector;

@Component({
  selector: "sr-barcode-scan",
  imports: [FormsModule, Icon, Modal],
  template: `
    <button class="btn" type="button" [disabled]="disabled()" (click)="show()"><sr-icon name="scan" />{{t(label())}}</button>
    @if(open()){
      <sr-modal [title]="t('Scan barcode')" (closed)="close()">
        <div class="workflow-stack">
          <div class="scan-preview" [hidden]="!camera()">
            <video #video muted playsinline [attr.aria-label]="t('Barcode camera preview')"></video>
            <span aria-hidden="true"></span>
          </div>
          @if(camera()){<p>{{t('Hold the bars upright. Move closer until the full barcode fills the guide and the bars look sharp.')}}</p>}
          @if(message()){<p role="status">{{t(message())}}</p>}
          <form class="modal-form" (ngSubmit)="accept(code)">
            <label>{{t('Barcode')}}
              <input name="barcode" [(ngModel)]="code" maxlength="27" autocomplete="off" autocapitalize="characters" />
            </label>
            <div class="button-group">
              <button class="btn primary" type="submit" [disabled]="!code.trim()">{{t('Find product')}}</button>
              @if(!camera()){<button class="btn" type="button" (click)="start()">{{t('Open camera')}}</button>}
            </div>
          </form>
        </div>
      </sr-modal>
    }
  `,
})
export class BarcodeScan implements OnDestroy {
  label = input("Scan barcode");
  disabled = input(false);
  readonly t = inject(Language).translate;
  scanned = output<string>();
  scanCompleted = output<ScanResult>();
  video = viewChild<ElementRef<HTMLVideoElement>>("video");
  open = signal(false);
  camera = signal(false);
  message = signal("");
  code = "";
  private readonly injector = inject(Injector);
  private stream?: MediaStream;
  private timer?: ReturnType<typeof setTimeout>;
  private request = 0;

  show() {
    this.code = "";
    this.open.set(true);
    afterNextRender(() => {
      if (this.open() && !this.camera()) void this.start();
    }, { injector: this.injector });
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      this.message.set("Camera access needs HTTPS. Enter the barcode or use a USB scanner.");
      return;
    }
    const request = ++this.request;
    this.camera.set(true);
    this.message.set("Opening the camera…");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } },
      });
      if (request !== this.request || !this.video()) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      this.stream = stream;
      const video = this.video()!.nativeElement;
      video.srcObject = stream;
      await video.play();
      if (request !== this.request) return;
      this.message.set("");
      this.watch(video, request);
    } catch {
      if (request !== this.request) return;
      this.stop();
      this.message.set("Could not open the camera. Check camera permission or enter the barcode.");
    }
  }

  private watch(video: HTMLVideoElement, request: number) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const NativeDetector = (globalThis as { BarcodeDetector?: DetectorConstructor }).BarcodeDetector;
    let detector: Detector | undefined;
    try {
      if (NativeDetector) detector = new NativeDetector({ formats: ["code_128"] });
    } catch {
      detector = undefined;
    }
    const scan = async () => {
      if (request !== this.request) return;
      let found: string | null = null;
      if (video.readyState >= 2) {
        try {
          found = (await detector?.detect(video))?.find(item => /^SR-[A-Z0-9-]{1,24}$/.test(item.rawValue))?.rawValue ?? null;
        } catch {
          detector = undefined;
        }
        if (!found && ctx) found = this.scanFrame(video, ctx);
      }
      if (request !== this.request) return;
      if (found) this.accept(found, "camera");
      else this.timer = setTimeout(scan, 180);
    };
    void scan();
  }

  private scanFrame(video: HTMLVideoElement, ctx: CanvasRenderingContext2D) {
    const width = video.videoWidth;
    if (!width) return null;
    if (ctx.canvas.width !== width) ctx.canvas.width = width;
    if (ctx.canvas.height !== 1) ctx.canvas.height = 1;
    const gray = new Uint8Array(width);
    for (const height of [0.5, 0.45, 0.55, 0.38, 0.62, 0.31, 0.69]) {
      ctx.drawImage(video, 0, Math.floor(video.videoHeight * height), width, 1, 0, 0, width, 1);
      const pixels = ctx.getImageData(0, 0, width, 1).data;
      for (let x = 0; x < width; x++) {
        gray[x] = (pixels[4 * x] + pixels[4 * x + 1] * 2 + pixels[4 * x + 2]) / 4;
      }
      const found = readBarcodeRow(gray);
      if (found) return found;
    }
    return null;
  }

  accept(value: string, source: ScanResult["source"] = "manual") {
    const code = value.trim().toUpperCase();
    if (!code) return;
    this.close();
    this.scanned.emit(code);
    this.scanCompleted.emit({ barcode: code, source });
  }

  close() {
    this.stop();
    this.open.set(false);
  }

  private stop() {
    ++this.request;
    clearTimeout(this.timer);
    this.stream?.getTracks().forEach(track => track.stop());
    this.stream = undefined;
    this.camera.set(false);
  }

  ngOnDestroy() {
    this.stop();
  }
}
