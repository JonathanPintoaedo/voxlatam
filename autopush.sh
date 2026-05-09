#!/bin/bash
cd ~/PROYECTOS/voxlatam
git add .
git diff --cached --quiet && echo "Sin cambios" && exit 0
git commit -m "auto: $(date '+%Y-%m-%d %H:%M')"
git push origin master
echo "✅ Subido a GitHub"
