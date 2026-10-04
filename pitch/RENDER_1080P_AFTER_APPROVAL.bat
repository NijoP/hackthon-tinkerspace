@echo off
setlocal
cd /d "%~dp0"
echo Super Monkey - 1920x1080 final render
echo Watch Super_Monkey_pitch_preview.mp4 first.
echo This renders 600 full-resolution frames and may take several minutes.
echo If the scene has changed, rename video_output\final_frames before rerendering.
choice /m "Have you approved the preview and want to render the finals"
if errorlevel 2 exit /b 0
set SM_MODE=FINAL
set SM_ACTION=RENDER
"%~dp0tools\blender-4.5.14-windows-x64\blender.exe" -b -t 10 --python-exit-code 1 --python "%~dp0phase2_video.py"
if errorlevel 1 goto fail
if not exist "%~dp0final.mp4" (
  "C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe" "%~dp0encode_video.py" --mode final
  if errorlevel 1 goto fail
)
echo Done. Open final.mp4 in this folder.
pause
exit /b 0
:fail
echo Rendering or encoding failed. Read the error above; completed frames are retained.
pause
exit /b 1
