import {
  Component,
  Input,
  Output,
  EventEmitter,
  HostListener,
  ElementRef,
  AfterViewInit,
  OnDestroy,
  inject,
} from "@angular/core";
import { Icon } from "./icon";
@Component({
  selector: "sr-modal",
  standalone: true,
  imports: [Icon],
  templateUrl: "./modal.html",
})
export class Modal implements AfterViewInit, OnDestroy {
  @Input() title = "";
  @Input() wide = false;
  @Output() closed = new EventEmitter<void>();
  el = inject(ElementRef);
  previous = document.activeElement as HTMLElement | null;
  ngAfterViewInit() {
    setTimeout(() =>
      this.el.nativeElement.querySelector("input,select,button")?.focus(),
    );
  }
  ngOnDestroy() {
    this.previous?.focus();
  }
  @HostListener("document:keydown", ["$event"]) key(e: KeyboardEvent) {
    if (e.key === "Escape") {
      this.closed.emit();
      return;
    }
    if (e.key === "Tab") {
      const items = Array.from(
        this.el.nativeElement.querySelectorAll(
          "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]",
        ),
      ) as HTMLElement[];
      const first = items[0],
        last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    }
  }
}
