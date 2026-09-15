from pathlib import Path
p=Path(__file__).resolve().parents[1]/'source/android/app/src/main/java/cz/pzrevize/mobile/MainActivity.java'
s=p.read_text(encoding='utf-8')
old='LinearLayout bl=new LinearLayout.LayoutParams(0,dp(48),1)'
new='LinearLayout.LayoutParams bl=new LinearLayout.LayoutParams(0,dp(48),1)'
if old not in s: raise SystemExit('compile fix pattern not found')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('compile fix OK')
