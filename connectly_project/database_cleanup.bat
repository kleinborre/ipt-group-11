@echo off
cd connectly_project

:: Deletes specific migration files, resets database, and runs Django migration commands.

REM Delete Python migration files except __init__.py
for /r %%G in (*\migrations\*.py) do (
    if /I not "%%~nxG" == "__init__.py" del "%%G"
)

REM Delete .pyc files in migrations
for /r %%G in (*\migrations\*.pyc) do del "%%G"

REM Delete SQLite database files
for /r %%G in (*db.sqlite3) do del "%%G"

REM Run Django migration commands
python manage.py makemigrations
python manage.py migrate --noinput

REM Reset auto-increment ID sequences
python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('''DELETE FROM sqlite_sequence WHERE name IN (SELECT name FROM sqlite_master WHERE type='table');''')"

REM Create a Django superuser
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@connectly.com', 'mmdc2025')"

echo Cleanup, ID reset, and migration completed.
pause