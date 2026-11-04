import { Component, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe, DecimalPipe } from "@angular/common";
import { Store, User } from "./store";
import { Icon } from "./icon";
@Component({
  standalone: true,
  imports: [FormsModule, DatePipe, DecimalPipe, Icon],
  templateUrl: "./settings.html",
})
export class Settings {
  s = inject(Store);
  async save(p: User) {
    await this.s.mutate(
      "/staff/" + p.staff_id,
      { role: p.role, is_active: p.is_active },
      "Staff access updated",
      "PATCH",
    );
  }
  async backup() {
    await this.s.mutate("/backups", {}, "Backup created and integrity checked");
  }
}
