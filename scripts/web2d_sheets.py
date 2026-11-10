from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/web2d-comparison';BASE=ROOT/'experiments/monuments-xhigh'
items=json.loads((BASE/'generation-summary.json').read_text())['results']
for i in items: shutil.copy2(BASE/(i['slug']+'.png'),OUT/(i['slug']+'-three.png'))
for page in range(2):
 sheet=Image.new('RGB',(1800,5*430),(240,242,245));d=ImageDraw.Draw(sheet)
 for row,item in enumerate(items[page*5:page*5+5]):
  d.text((10,row*430+6),item['name'],fill='black',font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',22))
  for col,fmt in enumerate(['three','canvas','svg']):
   im=Image.open(OUT/(item['slug']+'-'+fmt+'.png')).convert('RGB');im.thumbnail((594,396));sheet.paste(im,(col*600,row*430+32));d.text((col*600+10,row*430+34),fmt,fill='#cd1360',font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',16))
 sheet.save(OUT/f'contact-sheet-{page+1}.png')
# compact full-sheet suitable for download
all_sheet=Image.new('RGB',(1800,4300))
for page in range(2): all_sheet.paste(Image.open(OUT/f'contact-sheet-{page+1}.png'),(0,page*2150))
all_sheet.save(OUT/'contact-sheet.png')
