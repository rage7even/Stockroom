from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]
    operations = [
        migrations.RunSQL(
            "CREATE TRIGGER history_no_update BEFORE UPDATE ON stock_movement BEGIN SELECT RAISE(ABORT,'History is append-only'); END;",
            "DROP TRIGGER history_no_update;",
        ),
        migrations.RunSQL(
            "CREATE TRIGGER history_no_delete BEFORE DELETE ON stock_movement BEGIN SELECT RAISE(ABORT,'History is append-only'); END;",
            "DROP TRIGGER history_no_delete;",
        ),
    ]
