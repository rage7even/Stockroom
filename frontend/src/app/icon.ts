import { Component, Input } from "@angular/core";
@Component({
  selector: "sr-icon",
  standalone: true,
  templateUrl: "./icon.html",
  styles: [
    `
      :host {
        display: inline-flex;
        width: 20px;
        height: 20px;
        flex: none;
      }
      svg {
        width: 100%;
        height: 100%;
      }
    `,
  ],
})
export class Icon {
  @Input() name = "box";
  paths: Record<string, string> = {
    box: "M3 7 12 2l9 5v10l-9 5-9-5V7Zm0 0 9 5 9-5M12 12v10M7.5 4.5l9 5",
    grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
    orders: "M6 3h12v19l-3-2-3 2-3-2-3 2V3ZM9 7h6M9 11h6M9 15h3",
    receive: "M12 3v12m-4-4 4 4 4-4M4 14v6h16v-6",
    history: "M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2",
    users:
      "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
    settings:
      "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3",
    search: "M21 21l-5-5M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16",
    plus: "M12 5v14M5 12h14",
    arrow: "M5 12h14m-5-5 5 5-5 5",
    down: "m6 9 6 6 6-6",
    check: "m5 12 4 4L19 6",
    alert: "m12 3 10 18H2L12 3Zm0 6v5m0 3v.01",
    logout: "M9 21H3V3h6m6 4 5 5-5 5M8 12h12",
    close: "m6 6 12 12M6 18 18 6",
    mail: "M3 5h18v14H3V5Zm0 0 9 8 9-8",
    lock: "M5 10h14v11H5V10Zm3 0V6a4 4 0 0 1 8 0v4M12 14v3",
    cable: "M8 3v4m8-4v4M6 7h12v5a6 6 0 0 1-12 0V7Zm6 11v4",
    phone: "M7 2h10v20H7V2Zm4 17h2",
    audio: "M4 14v-3a8 8 0 0 1 16 0v3M4 12h3v8H4v-8Zm13 0h3v8h-3v-8",
    power: "M8 3h8v3h3v16H5V6h3V3Zm4 6-3 5h6l-3 5",
    menu: "M4 6h16M4 12h16M4 18h16",
    download: "M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4",
    edit: "m4 16 12-12 4 4L8 20H4v-4Zm9-9 4 4",
    shield: "M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4Zm-5 10 3 3 7-7",
  };
}
