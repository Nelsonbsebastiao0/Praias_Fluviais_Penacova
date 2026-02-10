@echo off
REM Script to deploy project to GitHub
cd /d "c:\Users\Utilizador\Downloads\praias_fluviais-main\praias_fluviais-main"

echo Initializing Git repository...
git init

echo Configuring remote origin...
git remote remove origin 2>nul
git remote add origin https://github.com/nelsonbsebastiao0/Praias_Fluviais_Penacova.git

echo Switching to main branch...
git branch -M main

echo Adding all files to staging...
git add .

echo Committing files...
git commit -m "Upload project files"

echo Pushing to GitHub...
git push -u origin main

echo done.
pause
