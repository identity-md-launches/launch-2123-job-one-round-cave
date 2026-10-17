/* One-use export of image-tool pigment onto inherited stone. No new shapes
 * are drawn here. The generated motif occupies the required output temporarily;
 * its pinned hash prevents rerunning this over an already finished wall.
 * Uses Node built-ins and the existing, unchanged workspace JPEG encoder.
 */
'use strict';
const fs = require('fs');
const zlib = require('zlib');
const crypto = require('crypto');
const assert = require('assert');
const encodeJPEG = require('./tools/corpus-change-receipt/vendor/jpeg-js/lib/encoder.js');
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const table = Array.from({length:256}, (_, n) => {
  for (let k=0;k<8;k++) n = (n & 1) ? 0xedb88320 ^ (n >>> 1) : n >>> 1;
  return n >>> 0;
});
function crc32(bytes) {
  let crc=0xffffffff;
  for (const b of bytes) crc=table[(crc ^ b)&255] ^ (crc>>>8);
  return (crc ^ 0xffffffff) >>> 0;
}
function readPNG(bytes) {
  assert(bytes.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex')));
  let width, height, channels;
  const parts=[];
  for (let at=8;at<bytes.length;) {
    const n=bytes.readUInt32BE(at), kind=bytes.toString('ascii',at+4,at+8);
    const body=bytes.subarray(at+8,at+8+n);
    assert.equal(crc32(bytes.subarray(at+4,at+8+n)),bytes.readUInt32BE(at+8+n));
    if (kind==='IHDR') {
      width=body.readUInt32BE(0);height=body.readUInt32BE(4);
      assert.equal(body[8],8);assert([2,6].includes(body[9]));
      assert.equal(body[10]+body[11]+body[12],0);
      channels=body[9]===2?3:4;
    } else if (kind==='IDAT') parts.push(body);
    else if (kind==='IEND') break;
    at+=n+12;
  }
  const stride=width*channels, packed=zlib.inflateSync(Buffer.concat(parts));
  assert.equal(packed.length,height*(stride+1));
  const pixels=Buffer.alloc(width*height*channels);
  for (let y=0;y<height;y++) {
    const filter=packed[y*(stride+1)];assert(filter<=4);
    for (let x=0;x<stride;x++) {
      const at=y*stride+x, left=x>=channels?pixels[at-channels]:0;
      const above=y?pixels[at-stride]:0, diagonal=y&&x>=channels?pixels[at-stride-channels]:0;
      let predictor=0;
      if (filter===1) predictor=left;
      if (filter===2) predictor=above;
      if (filter===3) predictor=(left+above)>>>1;
      if (filter===4) {
        const p=left+above-diagonal,a=Math.abs(p-left),b=Math.abs(p-above),c=Math.abs(p-diagonal);
        predictor=a<=b&&a<=c?left:b<=c?above:diagonal;
      }
      pixels[at]=(packed[y*(stride+1)+x+1]+predictor)&255;
    }
  }
  return {width,height,channels,pixels};
}
function writePNG(width,height,pixels) {
  function chunk(kind,body) {
    const data=Buffer.concat([Buffer.from(kind),body]),head=Buffer.alloc(4),tail=Buffer.alloc(4);
    head.writeUInt32BE(body.length);tail.writeUInt32BE(crc32(data));
    return Buffer.concat([head,data,tail]);
  }
  const header=Buffer.alloc(13);header.writeUInt32BE(width,0);header.writeUInt32BE(height,4);
  header[8]=8;header[9]=2;
  const raw=Buffer.alloc(height*(width*3+1));
  for(let y=0;y<height;y++) pixels.copy(raw,y*(width*3+1)+1,y*width*3,(y+1)*width*3);
  return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',header),
    chunk('IDAT',zlib.deflateSync(raw,{level:9})),chunk('IEND',Buffer.alloc(0))]);
}
function main() {
  const ancestorPath='artifacts/line-3/wall-v10.png', outputPath='artifacts/line-3/wall-v11.png';
  const oldBytes=fs.readFileSync(ancestorPath),draftBytes=fs.readFileSync(outputPath);
  assert.equal(hash(oldBytes),'6f73df1ec748dd65c1f4755934c54be0fd6328fec7f689e683b21b90dedddb42');
  assert.equal(hash(draftBytes),'11d9718a479cc8b35e8cf13bddce2ed8cb6dd4bd5df989969d391074ef3c20d5',
    'expected fresh generated motif; refusing to replace a finished wall');
  assert(!fs.existsSync('dist/line-3/31.json'));
  assert(!fs.existsSync('dist/line-3/31.jpg'));
  const old=readPNG(oldBytes),draft=readPNG(draftBytes);
  assert.deepEqual([old.width,old.height,old.channels],[1254,1254,3]);
  assert.deepEqual([draft.width,draft.height,draft.channels],[1983,793,4]);
  let minX=draft.width,minY=draft.height,maxX=0,maxY=0;
  for(let y=0;y<draft.height;y++) for(let x=0;x<draft.width;x++) {
    if(draft.pixels[(y*draft.width+x)*4+3]>180) {
      minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
    }
  }
  const x0=425,y0=780,mw=220,mh=70,final=Buffer.from(old.pixels);
  for(let y=0;y<mh;y++) for(let x=0;x<mw;x++) {
    const sx=minX+Math.floor(x*(maxX-minX+1)/mw),sy=minY+Math.floor(y*(maxY-minY+1)/mh);
    const at=(sy*draft.width+sx)*4;
    const [r,g,b,a]=draft.pixels.subarray(at,at+4);
    // Transfer generated pigment only, flattening its palette and allowing
    // the actual ancestor stone to show through worn gaps. No background moves.
    const alpha=Math.max(0,(a-160)/95)*.72;
    if(!alpha||(x*17+y*29)%13<3) continue;
    const color=r>g*1.5?[151,62,31]:r>g*1.15&&g>b*1.2?[176,118,46]:[43,31,22];
    const target=((y0+y)*old.width+x0+x)*3;
    for(let c=0;c<3;c++) final[target+c]=Math.round(old.pixels[target+c]*(1-alpha)+color[c]*alpha);
  }
  let changed=0,outside=0;
  for(let n=0;n<old.width*old.height;n++) {
    if(!final.subarray(n*3,n*3+3).equals(old.pixels.subarray(n*3,n*3+3))) {
      changed++;
      if(!(n%old.width>=x0&&n%old.width<x0+mw&&Math.floor(n/old.width)>=y0&&Math.floor(n/old.width)<y0+mh)) outside++;
    }
  }
  assert(changed>0);assert.equal(outside,0);
  const png=writePNG(old.width,old.height,final);
  assert(readPNG(png).pixels.equals(final));
  const rgba=Buffer.alloc(512*512*4);
  for(let y=0;y<512;y++) for(let x=0;x<512;x++) {
    const xa=Math.floor(x*old.width/512),xb=Math.floor((x+1)*old.width/512);
    const ya=Math.floor(y*old.height/512),yb=Math.floor((y+1)*old.height/512);
    for(let c=0;c<3;c++) {
      let sum=0;
      for(let sy=ya;sy<yb;sy++) for(let sx=xa;sx<xb;sx++) sum+=final[(sy*old.width+sx)*3+c];
      rgba[(y*512+x)*4+c]=Math.round(sum/((xb-xa)*(yb-ya)));
    }
    rgba[(y*512+x)*4+3]=255;
  }
  const jpeg=encodeJPEG({data:rgba,width:512,height:512},77).data;
  assert(jpeg.length<100000);
  assert.equal(fs.readlinkSync('artifacts/line-3/wall.png'),'wall-v10.png');
  fs.writeFileSync(outputPath,png);
  fs.unlinkSync('artifacts/line-3/wall.png');fs.symlinkSync('wall-v11.png','artifacts/line-3/wall.png');
  fs.writeFileSync('dist/line-3/31.jpg',jpeg,{flag:'wx'});
  const report={wall:outputPath,format:'PNG',dimensions:[old.width,old.height],mode:'RGB',sha256:hash(png),
    ancestor_sha256:hash(oldBytes),generated_motif_sha256:hash(draftBytes),
    generated_motif_dimensions:[draft.width,draft.height],generated_crop:[minX,minY,maxX-minX+1,maxY-minY+1],
    new_mark_rectangle:[x0,y0,mw,mh],changed_pixels:changed,changed_pixels_outside_rectangle:outside,
    thumbnail:{path:'dist/line-3/31.jpg',format:'JPEG',dimensions:[512,512],bytes:jpeg.length},
    visual_review:'pending',unmet_visual_requirements:[]};
  fs.writeFileSync('line-3/IMAGE-31.json',JSON.stringify(report,null,2)+'\n');
  const record={name:'The Surrounding Stones',image:'https://api.imd.fun/artifacts/'+hash(png),
    attributes:[['Cave','Crystal'],['Wall','Line 3'],['Number',31],['Left behind','Citation Context'],
      ['Meaning','A red stone held among its neighbors marks a cited passage read with its surrounding lines.'],
      ['One thing','Offline document search with exact source line citations']].map(([trait_type,value])=>({trait_type,value}))};
  fs.writeFileSync('dist/line-3/31.json',JSON.stringify(record,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify(report,null,2));
}
if(require.main===module) main();
module.exports={readPNG};
