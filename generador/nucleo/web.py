"""Genera la web estática (carpeta 'sitio') a partir de los pueblos guardados."""
import html
import json
import shutil
import time
from pathlib import Path

from . import mapa
from .datos import Almacen, normalizar, slugify

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def e(texto) -> str:
    return html.escape(str(texto or ""), quote=True)


def fecha_larga(iso: str) -> str:
    """'2024-05-12' -> '12 de mayo de 2024'; admite '2024-05' y '2024'."""
    partes = (iso or "").split("-")
    try:
        if len(partes) == 3:
            return f"{int(partes[2])} de {MESES[int(partes[1]) - 1]} de {partes[0]}"
        if len(partes) == 2:
            return f"{MESES[int(partes[1]) - 1]} de {partes[0]}"
    except (ValueError, IndexError):
        pass
    return iso or ""


def con_articulo(iso: str) -> str:
    """Para frases: 'el 12 de mayo de 2024', 'en mayo de 2024', 'en 2024'."""
    return ("el " if len((iso or "").split("-")) == 3 else "en ") + fecha_larga(iso)


def fecha_corta(iso: str) -> str:
    partes = (iso or "").split("-")
    try:
        if len(partes) >= 2:
            return f"{MESES[int(partes[1]) - 1].capitalize()} {partes[0]}"
    except (ValueError, IndexError):
        return ""
    return partes[0] if partes and partes[0].isdigit() else ""


def parrafos(texto: str) -> str:
    bloques = [b.strip() for b in (texto or "").replace("\r", "").split("\n\n") if b.strip()]
    return "\n".join(f"<p>{e(b).replace(chr(10), '<br>')}</p>" for b in bloques)


def numero(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _orden_comunidad(c: str):
    return (c in ("", "Sin clasificar", "Fuera de España"), normalizar(c))


# ---------------------------------------------------------------------------- CSS
CSS = r"""
:root{
  --papel:#f5efe3; --papel-2:#ece3d2; --tinta:#2a2621; --tinta-2:#6b6257;
  --acento:#a8472a; --acento-2:#7c6a3b; --linea:#d8ccb6; --tarjeta:#fffaf0;
  --sombra:0 1px 2px rgba(60,40,20,.08),0 6px 18px rgba(60,40,20,.08);
  --radio:10px; --ancho:1180px;
  --f-titulo:"Fraunces",Georgia,"Times New Roman",serif;
  --f-texto:"Source Sans 3","Segoe UI",system-ui,sans-serif;
}
@media (prefers-color-scheme:dark){
  :root{--papel:#1c1a17;--papel-2:#26231f;--tinta:#efe7d8;--tinta-2:#b3a893;
    --acento:#e0835f;--acento-2:#c9b27a;--linea:#3a352e;--tarjeta:#24211d;
    --sombra:0 1px 2px rgba(0,0,0,.4),0 6px 18px rgba(0,0,0,.35)}
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--papel);color:var(--tinta);font:17px/1.6 var(--f-texto)}
img{max-width:100%;display:block}
a{color:var(--acento)}
.envoltorio{max-width:var(--ancho);margin:0 auto;padding:0 20px}

/* ---- cabecera portada ---- */
.cabecera{padding:64px 0 36px;border-bottom:1px solid var(--linea)}
.cabecera .sello{font:600 12px/1 var(--f-texto);letter-spacing:.18em;text-transform:uppercase;color:var(--acento)}
.cabecera h1{font:600 clamp(40px,7vw,76px)/1 var(--f-titulo);margin:14px 0 12px;letter-spacing:-.02em}
.cabecera p{margin:0;color:var(--tinta-2);font-size:19px;max-width:42ch}
.cifras{display:flex;gap:28px;flex-wrap:wrap;margin-top:28px}
.cifras div{font:600 30px/1 var(--f-titulo)}
.cifras span{display:block;font:500 13px/1.4 var(--f-texto);color:var(--tinta-2);text-transform:uppercase;letter-spacing:.08em;margin-top:6px}

/* ---- cabecera con dibujo (de día; de noche en modo oscuro) ---- */
.cabecera.con-dibujo{position:relative;overflow:hidden;padding-bottom:0;border-bottom:0;
  background:linear-gradient(180deg,var(--cielo-1),var(--cielo-2) 55%,var(--papel))}
.con-dibujo .envoltorio{position:relative;z-index:2}
.paisaje{position:relative;height:clamp(150px,21vw,300px);margin-top:-10px;overflow:hidden}
.paisaje svg{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:max(100%,900px);height:auto}
:root{--cielo-1:#f7d9a8;--cielo-2:#f8ead2;--astro:#f3a65f;--nube:#fffaf0;--colina1:#d9b48a;--colina2:#b98a5e;--colina3:#8f6a45;
  --pared:#f2e6cf;--pared2:#e9d9bd;--tejado:#a8472a;--tejado2:#b8532f;--tejado3:#c2633a;--ventana:#6b4630;--arbol:#4f6b3a;--camino:#e8d3ae}
.paisaje .astro{fill:var(--astro)}.paisaje .nubes{fill:var(--nube);opacity:.75}.paisaje .estrellas{fill:#fff;opacity:0}
.paisaje .colina1{fill:var(--colina1)}.paisaje .colina2{fill:var(--colina2)}.paisaje .colina3{fill:var(--colina3)}
.paisaje .pared{fill:var(--pared)}.paisaje .pared2{fill:var(--pared2)}.paisaje .tejado{fill:var(--tejado)}
.paisaje .tejado2{fill:var(--tejado2)}.paisaje .tejado3{fill:var(--tejado3)}.paisaje .ventana,.paisaje .campana,.paisaje .puerta{fill:var(--ventana)}
.paisaje .arbol{fill:var(--arbol)}.paisaje .camino{stroke:var(--camino);stroke-width:10;fill:none;stroke-linecap:round;opacity:.8}
.paisaje .suelo{fill:var(--papel)}
@media (prefers-color-scheme:dark){
  :root{--cielo-1:#0f1830;--cielo-2:#1d2236;--astro:#f1e6c8;--nube:#3a3f55;--colina1:#2c2e3b;--colina2:#24252f;--colina3:#1d1d24;
    --pared:#585060;--pared2:#4b4452;--tejado:#6b3a35;--tejado2:#73403a;--tejado3:#7a4840;--ventana:#ffcf6b;--arbol:#1f2b22;--camino:#3b3a44}
  .paisaje .estrellas{opacity:.85}.paisaje .nubes{opacity:.35}
  .paisaje .campana,.paisaje .puerta{fill:#2a2230}
  .cabecera.con-dibujo .sello{color:#f0a37f}
}
@media (prefers-reduced-motion:no-preference){
  .paisaje .nubes{animation:nubes 60s linear infinite alternate}
  @keyframes nubes{to{transform:translateX(60px)}}
}

/* ---- filtros ---- */
.filtros{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--papel) 92%,transparent);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--linea)}
.filtros .envoltorio{display:flex;gap:12px;align-items:center;padding-top:12px;padding-bottom:12px;flex-wrap:wrap}
.filtros input{flex:1 1 220px;min-width:0;font:inherit;padding:9px 14px;border:1px solid var(--linea);
  border-radius:999px;background:var(--tarjeta);color:var(--tinta)}
.chips{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;flex:1 1 100%}
.chips::-webkit-scrollbar{display:none}
.chips button{font:500 14px var(--f-texto);white-space:nowrap;padding:6px 12px;border-radius:999px;
  border:1px solid var(--linea);background:transparent;color:var(--tinta);cursor:pointer}
.chips button[aria-pressed=true]{background:var(--tinta);color:var(--papel);border-color:var(--tinta)}

/* ---- grupos y fichas ---- */
.comunidad{padding:44px 0 8px;scroll-margin-top:110px}
.comunidad>h2{font:600 34px/1.1 var(--f-titulo);margin:0 0 4px;display:flex;align-items:baseline;gap:12px}
.comunidad>h2 small{font:500 15px var(--f-texto);color:var(--tinta-2)}
.provincia h3{font:600 13px/1 var(--f-texto);letter-spacing:.14em;text-transform:uppercase;color:var(--acento-2);
  margin:22px 0 14px;display:flex;align-items:center;gap:10px}
.provincia h3::after{content:"";flex:1;height:1px;background:var(--linea)}
.rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:20px}
.ficha{display:block;text-decoration:none;color:inherit;background:var(--tarjeta);border-radius:var(--radio);
  overflow:hidden;box-shadow:var(--sombra);transition:transform .2s,box-shadow .2s}
.ficha:hover{transform:translateY(-3px)}
.ficha .foto{aspect-ratio:4/3;background:var(--papel-2);overflow:hidden}
.ficha .foto img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
.ficha:hover .foto img{transform:scale(1.04)}
.ficha .sinfoto{width:100%;height:100%;display:grid;place-items:center;font:600 44px var(--f-titulo);color:var(--linea)}
.ficha .texto{padding:12px 14px 14px}
.ficha h4{font:600 20px/1.2 var(--f-titulo);margin:0}
.ficha p{margin:4px 0 0;font-size:14px;color:var(--tinta-2)}
.vacio{padding:60px 0;text-align:center;color:var(--tinta-2)}

/* ---- página de pueblo ---- */
.heroe{position:relative;min-height:min(70vh,620px);display:flex;align-items:flex-end;color:#fff;background:#3a332b}
.heroe img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.heroe::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.25),rgba(0,0,0,0) 30%,rgba(0,0,0,.65))}
.heroe .envoltorio{position:relative;z-index:1;width:100%;padding-bottom:40px}
.heroe.sin-foto{min-height:260px;background:var(--papel-2);color:var(--tinta)}
.heroe.sin-foto::after{display:none}
.volver{position:absolute;top:18px;left:20px;z-index:2;color:inherit;text-decoration:none;font-weight:600;
  background:rgba(0,0,0,.35);padding:6px 14px;border-radius:999px;font-size:15px}
.heroe.sin-foto .volver{background:var(--tarjeta)}
.heroe .lugar{font:600 13px/1 var(--f-texto);letter-spacing:.16em;text-transform:uppercase;opacity:.9}
.heroe h1{font:600 clamp(42px,8vw,88px)/1 var(--f-titulo);margin:12px 0 10px;letter-spacing:-.02em}
.heroe .visitas{font-size:17px;opacity:.92}
.cuerpo{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:48px;padding:44px 20px 20px}
@media (max-width:860px){.cuerpo{grid-template-columns:1fr;gap:28px}}
.cuerpo h2{font:600 26px/1.2 var(--f-titulo);margin:0 0 12px}
.cuerpo section+section{margin-top:36px}
.cuerpo p{margin:0 0 14px}
.notas{background:var(--tarjeta);border-left:4px solid var(--acento);padding:18px 22px;border-radius:0 var(--radio) var(--radio) 0;box-shadow:var(--sombra)}
.notas h2{font-size:21px}
.nota-ia{font-size:13px;color:var(--tinta-2)}
.wiki{color:var(--tinta-2)}
.wiki .fuente,.cuerpo .fuente{font-size:14px;color:var(--tinta-2)}
.lugares{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-bottom:8px}
.lugar{display:flex;flex-direction:column;background:var(--tarjeta);border-radius:10px;overflow:hidden;box-shadow:var(--sombra);
  text-decoration:none;color:var(--tinta);transition:transform .2s}
.lugar:hover{transform:translateY(-2px)}
.lugar img{width:100%;aspect-ratio:4/3;object-fit:cover}
.lugar .credito{padding:4px 10px 0;font-size:11px}
.lugar b{padding:6px 10px 10px;font-size:15px;line-height:1.3}
.lugar.sin-img{align-self:start}
.lugar.sin-img b{padding:14px 12px;border-left:3px solid var(--acento)}
.saber-mas details{background:var(--tarjeta);border-radius:10px;margin-bottom:8px;box-shadow:var(--sombra);overflow:hidden}
.saber-mas summary{cursor:pointer;padding:12px 16px;font:600 18px var(--f-titulo);list-style:none;display:flex;gap:10px;align-items:center}
.saber-mas summary::-webkit-details-marker{display:none}
.saber-mas summary::after{content:"+";margin-left:auto;font:400 22px var(--f-texto);color:var(--tinta-2)}
.saber-mas details[open] summary::after{content:"–"}
.saber-mas details>p{padding:0 16px;margin:0 0 12px}
.saber-mas details>p:last-child{padding-bottom:6px}
.datos{background:var(--tarjeta);border-radius:var(--radio);padding:22px;box-shadow:var(--sombra);align-self:start;position:sticky;top:20px}
.datos .escudo{width:84px;margin:0 auto 14px}
.datos dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:8px 14px;font-size:15px}
.datos dt{color:var(--tinta-2)}
.datos dd{margin:0;text-align:right;font-weight:600}
.datos .enlaces{margin-top:16px;display:flex;flex-direction:column;gap:6px;font-size:15px}
.galeria{padding:10px 20px 40px}
.galeria h2{font:600 26px/1.2 var(--f-titulo);margin:0 0 16px}
.mosaico{columns:3 260px;column-gap:12px}
.mosaico figure{margin:0 0 12px;break-inside:avoid}
.mosaico a.ampliar{display:block;border-radius:8px;overflow:hidden;cursor:zoom-in}
.mosaico figcaption{font-size:14px;color:var(--tinta-2);padding:6px 2px 0}
.credito{font-size:12px;color:var(--tinta-2)}
.credito a{color:inherit}
.credito-heroe{position:absolute;right:12px;bottom:8px;z-index:1;font-size:11px;opacity:.85;max-width:60%;text-align:right}
.credito-heroe a{color:inherit}
.vecinos{display:flex;justify-content:space-between;gap:16px;border-top:1px solid var(--linea);padding:22px 20px}
.vecinos a{text-decoration:none;font-weight:600;max-width:48%}
.vecinos small{display:block;color:var(--tinta-2);font-weight:500}

/* ---- visor ---- */
.visor{position:fixed;inset:0;z-index:50;background:rgba(10,8,6,.94);display:none;align-items:center;justify-content:center}
.visor.abierto{display:flex}
.visor img{max-width:94vw;max-height:86vh;object-fit:contain}
.visor p{position:absolute;bottom:14px;left:0;right:0;text-align:center;color:#ddd;margin:0;font-size:15px}
.visor button{position:absolute;background:none;border:0;color:#fff;font-size:42px;cursor:pointer;padding:16px;line-height:1}
.visor .cerrar{top:6px;right:10px;font-size:34px}
.visor .ant{left:4px}.visor .sig{right:4px}

/* ---- mapa de rascar ---- */
:root{--rasca:#cfc6b4;--rasca-2:#bdb29c;--pendiente:#2f6f6a}
@media (prefers-color-scheme:dark){:root{--rasca:#3b3630;--rasca-2:#4a443c;--pendiente:#7fc4bb}}
.mapa-sec{padding-top:40px;padding-bottom:10px}
.mapa-cab{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;margin-bottom:14px}
.mapa-cab h2{font:600 34px/1.1 var(--f-titulo);margin:0}
.mapa-cab p{margin:4px 0 0;color:var(--tinta-2)}
.progreso{width:min(320px,100%)}
.progreso .barra{height:8px;border-radius:99px;background:var(--papel-2);overflow:hidden}
.progreso .barra i{display:block;height:100%;width:0;background:var(--acento);border-radius:99px;transition:width 1.6s cubic-bezier(.2,.8,.2,1)}
.progreso small{display:block;margin-top:6px;color:var(--tinta-2);font-size:14px;text-align:right}
.mapa-marco{position:relative;background:var(--tarjeta);border-radius:16px;box-shadow:var(--sombra);overflow:hidden}
.mapa-marco svg{display:block;width:100%;height:auto;touch-action:manipulation}
.prov{fill:var(--rasca);stroke:var(--papel);stroke-width:.8;transition:fill .2s}
.prov.tapada{fill:url(#rascado)}
.prov.tapada:hover{fill:var(--rasca-2)}
.prov.destapada{fill:transparent;stroke:var(--tarjeta);stroke-width:1.2;cursor:pointer}
.prov.destapada:hover{fill:rgba(255,255,255,.18)}
.prov.solo-color{fill:var(--acento);opacity:.75}
.foto-prov{opacity:0;transition:opacity 1.2s ease}
.foto-prov.ver{opacity:1}
.velo{fill:var(--rasca);pointer-events:none;transition:opacity 1.2s ease}
.borde-canarias{fill:none;stroke:var(--linea);stroke-width:1}
.chincheta{cursor:pointer;transition:transform .15s}
.chincheta:hover{transform:scale(1.5)}
.chincheta.visitado circle{fill:var(--acento);stroke:#fff;stroke-width:1.5}
.chincheta.pendiente circle{fill:var(--tarjeta);stroke:var(--pendiente);stroke-width:2.2;stroke-dasharray:3 2}
.mapa-marco.sin-pendientes .chincheta.pendiente{display:none}
.globo{position:absolute;pointer-events:none;background:var(--tinta);color:var(--papel);padding:7px 11px;border-radius:8px;
  font-size:14px;line-height:1.35;max-width:240px;opacity:0;transform:translate(-50%,calc(-100% - 12px));transition:opacity .12s;z-index:3}
.globo b{font-family:var(--f-titulo);font-size:16px}
.globo.ver{opacity:1}
.mapa-pie{display:flex;gap:18px;flex-wrap:wrap;align-items:center;padding:12px 16px;border-top:1px solid var(--linea);font-size:14px;color:var(--tinta-2)}
.mapa-pie .muestra{display:inline-block;width:12px;height:12px;border-radius:50%;vertical-align:-1px;margin-right:6px}
.mapa-pie .m-vis{background:var(--acento);border:2px solid #fff}
.mapa-pie .m-pen{border:2px dashed var(--pendiente)}
.mapa-pie .m-tap{background:var(--rasca);border-radius:3px}
.mapa-pie label{margin-left:auto;cursor:pointer;display:flex;align-items:center;gap:6px}
.panel-prov{padding:14px 16px;border-top:1px solid var(--linea);display:none}
.panel-prov.ver{display:block}
.panel-prov h3{font:600 22px var(--f-titulo);margin:0 0 6px}
.panel-prov ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.panel-prov li a{display:inline-block;padding:5px 12px;border-radius:99px;background:var(--papel-2);text-decoration:none;color:var(--tinta);font-size:15px}
.panel-prov li.pend a{background:transparent;border:1.5px dashed var(--pendiente);color:var(--pendiente)}
.etiqueta-pend{display:inline-block;font:600 12px/1 var(--f-texto);letter-spacing:.12em;text-transform:uppercase;
  padding:6px 10px;border-radius:99px;border:1.5px dashed currentColor;margin-top:10px}
.pendientes{padding-top:44px;padding-bottom:8px}
.pendientes>h2{font:600 34px/1.1 var(--f-titulo);margin:0 0 4px}
.pendientes>p{color:var(--tinta-2);margin:0 0 18px}
.ficha.pend{background:transparent;border:2px dashed var(--linea);box-shadow:none}
.ficha.pend .foto img{filter:grayscale(.6) opacity(.85)}
footer{border-top:1px solid var(--linea);margin-top:40px;padding:26px 0 40px;color:var(--tinta-2);font-size:14px}
"""

JS_INDICE = r"""
(function(){
  var q=document.getElementById('buscar'), chips=document.querySelectorAll('.chips button'), actual='';
  function filtrar(){
    var t=(q.value||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
    document.querySelectorAll('.comunidad').forEach(function(sec){
      var okc=!actual||sec.dataset.comunidad===actual, vis=0;
      sec.querySelectorAll('.provincia').forEach(function(pr){
        var n=0;
        pr.querySelectorAll('.ficha').forEach(function(f){
          var ok=okc&&(!t||f.dataset.buscar.indexOf(t)>-1); f.hidden=!ok; if(ok)n++;});
        pr.hidden=!n; vis+=n;});
      sec.hidden=!vis;});
    var nada=document.getElementById('nada'); if(nada) nada.hidden=!!document.querySelector('.ficha:not([hidden])');
  }
  q&&q.addEventListener('input',filtrar);
  chips.forEach(function(b){b.addEventListener('click',function(){
    actual=b.dataset.c; chips.forEach(function(x){x.setAttribute('aria-pressed',x===b)}); filtrar();});});
})();
"""

JS_MAPA = r"""
(function(){
  var datos=JSON.parse(document.getElementById('datos-mapa').textContent);
  var marco=document.querySelector('.mapa-marco'); if(!marco||!window.d3||!window.PROVINCIAS_ES) return;
  var W=960,H=620, svg=d3.select(marco).insert('svg',':first-child').attr('viewBox','0 0 '+W+' '+H)
      .attr('role','img').attr('aria-label','Mapa de las provincias visitadas');
  var globo=d3.select(marco).append('div').attr('class','globo');
  var defs=svg.append('defs');
  var pat=defs.append('pattern').attr('id','rascado').attr('patternUnits','userSpaceOnUse').attr('width',6).attr('height',6)
      .attr('patternTransform','rotate(45)');
  pat.append('rect').attr('width',6).attr('height',6).attr('style','fill:var(--rasca)');
  pat.append('line').attr('x1',0).attr('y1',0).attr('x2',0).attr('y2',6).attr('style','stroke:var(--rasca-2);stroke-width:1.2');
  var panel=document.querySelector('.panel-prov');

  function verGlobo(ev,html){var r=marco.getBoundingClientRect(); globo.html(html).classed('ver',true)
     .style('left',(ev.clientX-r.left)+'px').style('top',(ev.clientY-r.top)+'px');}
  function ocultar(){globo.classed('ver',false);}

  (function(geo){
    var proy=d3.geoConicConformalSpain().fitExtent([[10,10],[W-10,H-10]],geo), ruta=d3.geoPath(proy);
    var capaFotos=svg.append('g'), capaProv=svg.append('g'), capaVelo=svg.append('g'), capaPins=svg.append('g');
    svg.append('path').attr('class','borde-canarias').attr('d',proy.getCompositionBorders());
    var orden=0;
    geo.features.forEach(function(f){
      var info=datos.prov[f.id], d=ruta(f);
      if(info&&info.foto){
        var b=ruta.bounds(f), id='c'+f.id;
        defs.append('clipPath').attr('id',id).append('path').attr('d',d);
        var img=capaFotos.append('image').attr('class','foto-prov').attr('href',info.foto)
          .attr('x',b[0][0]).attr('y',b[0][1]).attr('width',b[1][0]-b[0][0]).attr('height',b[1][1]-b[0][1])
          .attr('preserveAspectRatio','xMidYMid slice').attr('clip-path','url(#'+id+')');
        var velo=capaVelo.append('path').attr('class','velo').attr('d',d);
        (function(img,velo,n){setTimeout(function(){img.classed('ver',true);velo.style('opacity',0);},400+n*160);})(img,velo,orden++);
      }
      capaProv.append('path').attr('d',d)
        .attr('class','prov '+(info?(info.foto?'destapada':'destapada solo-color'):'tapada'))
        .on('mousemove',function(ev){
          var t='<b>'+f.properties.nombre+'</b>';
          if(info) t+='<br>'+info.n+(info.n==1?' pueblo visitado':' pueblos visitados');
          else t+='<br>Sin destapar';
          if(datos.pend[f.id]) t+='<br>'+datos.pend[f.id]+' por visitar';
          verGlobo(ev,t);})
        .on('mouseleave',ocultar)
        .on('click',function(){mostrarPanel(f);});
    });
    datos.pueblos.forEach(function(p){
      if(p.lat==null) return; var xy=proy([p.lon,p.lat]); if(!xy) return;
      var g=capaPins.append('g').attr('class','chincheta '+p.estado)
        .attr('transform','translate('+xy[0]+','+xy[1]+')').style('transform-origin',xy[0]+'px '+xy[1]+'px');
      g.append('circle').attr('r',p.estado=='pendiente'?5:4.5);
      g.on('mousemove',function(ev){verGlobo(ev,'<b>'+p.nombre+'</b><br>'+(p.estado=='pendiente'?'Por visitar':(p.fecha||'Visitado')));})
       .on('mouseleave',ocultar).on('click',function(){location.href=p.url;});
    });
  })(window.PROVINCIAS_ES);

  function mostrarPanel(f){
    var lista=datos.pueblos.filter(function(p){return p.prov==f.id;});
    var html='<h3>'+f.properties.nombre+'</h3>';
    if(!lista.length) html+='<p style="margin:0;color:var(--tinta-2)">Todavía no has estado aquí.</p>';
    else html+='<ul>'+lista.map(function(p){return '<li class="'+(p.estado=='pendiente'?'pend':'')+'"><a href="'+p.url+'">'+p.nombre+
      (p.estado=='pendiente'?' · por visitar':'')+'</a></li>';}).join('')+'</ul>';
    panel.innerHTML=html; panel.classList.add('ver');
  }
  var cb=document.getElementById('ver-pendientes');
  if(cb) cb.addEventListener('change',function(){marco.classList.toggle('sin-pendientes',!cb.checked);});
  var barra=document.querySelector('.progreso .barra i');
  if(barra) setTimeout(function(){barra.style.width=barra.dataset.w;},300);
})();
"""

JS_VISOR = r"""
(function(){
  var enlaces=[].slice.call(document.querySelectorAll('.mosaico a.ampliar')); if(!enlaces.length) return;
  var v=document.querySelector('.visor'), img=v.querySelector('img'), pie=v.querySelector('p'), i=0;
  function ver(n){i=(n+enlaces.length)%enlaces.length; img.src=enlaces[i].href; pie.textContent=enlaces[i].dataset.pie||''; v.classList.add('abierto');}
  function cerrar(){v.classList.remove('abierto'); img.removeAttribute('src');}
  enlaces.forEach(function(a,n){a.addEventListener('click',function(ev){ev.preventDefault();ver(n);});});
  v.querySelector('.cerrar').onclick=cerrar; v.querySelector('.ant').onclick=function(){ver(i-1)}; v.querySelector('.sig').onclick=function(){ver(i+1)};
  v.addEventListener('click',function(ev){if(ev.target===v)cerrar();});
  document.addEventListener('keydown',function(ev){if(!v.classList.contains('abierto'))return;
    if(ev.key==='Escape')cerrar(); if(ev.key==='ArrowLeft')ver(i-1); if(ev.key==='ArrowRight')ver(i+1);});
})();
"""


def _pagina(titulo: str, cuerpo: str, raiz: str, descripcion: str = "", js: str = "", scripts=()) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{raiz}estilo.css">
</head>
<body>
{cuerpo}
{''.join(f'<script src="{raiz}{x}"></script>' for x in scripts)}
{f'<script>{js}</script>' if js else ''}
</body>
</html>
"""


def credito_texto(f: dict) -> str:
    c = f.get("credito") or {}
    return f"Foto: {c.get('autor', '')} · {c.get('licencia', '')} · Wikimedia Commons" if c else ""


def credito_html(f: dict) -> str:
    c = f.get("credito") or {}
    if not c:
        return ""
    lic = e(c.get("licencia"))
    if c.get("url_licencia"):
        lic = f'<a href="{e(c["url_licencia"])}">{lic}</a>'
    return (f'Foto: <a href="{e(c.get("fuente"))}">{e(c.get("autor"))}</a> · {lic} · Wikimedia Commons')


def _pie(cfg) -> str:
    autor = f" · {e(cfg.get('autor'))}" if cfg.get("autor") else ""
    return (f'<footer><div class="envoltorio">{e(cfg.get("titulo_web"))}{autor} · '
            f'Textos de <a href="https://es.wikipedia.org">Wikipedia</a> con licencia '
            f'<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.es">CC BY-SA 4.0</a> · '
            f'Algunas fotos son de <a href="https://commons.wikimedia.org">Wikimedia Commons</a>; '
            f'su autor y licencia figuran junto a cada una · Mapa: <a href="https://github.com/martgnz/es-atlas">es-atlas</a> · Actualizado el {fecha_larga(time.strftime("%Y-%m-%d"))}</div></footer>')


# ---------------------------------------------------------------------------- índice
def _ficha(p: dict) -> str:
    buscar = normalizar(f"{p['nombre']} {p['provincia']} {p['comunidad']}")
    pendiente = p.get("estado") == "pendiente"
    if p.get("portada"):
        foto = f'<img src="pueblos/{e(p["slug"])}/mini/{e(p["portada"])}" alt="" loading="lazy">'
    else:
        foto = f'<div class="sinfoto">{e(p["nombre"][:1])}</div>'
    visita = fecha_corta(p["fechas_visita"][-1]) if p.get("fechas_visita") else "Visitado"
    if pendiente:
        visita = p["provincia"] or "Por visitar"
    return (f'<a class="ficha{" pend" if pendiente else ""}" href="pueblos/{e(p["slug"])}/index.html" data-buscar="{e(buscar)}">'
            f'<div class="foto">{foto}</div><div class="texto"><h4>{e(p["nombre"])}</h4>'
            f'<p>{e(visita) or "&nbsp;"}</p></div></a>')


def _datos_mapa(visitados: list, pendientes: list) -> dict:
    prov, pend, lista = {}, {}, []
    for p in sorted(visitados, key=lambda x: x.get("fechas_visita")[-1] if x.get("fechas_visita") else ""):
        pid = p.get("_prov")
        if pid:
            info = prov.setdefault(pid, {"n": 0, "foto": ""})
            info["n"] += 1
            if p.get("portada"):      # la foto del pueblo visitado más reciente
                info["foto"] = f"pueblos/{p['slug']}/mini/{p['portada']}"
    for p in pendientes:
        if p.get("_prov"):
            pend[p["_prov"]] = pend.get(p["_prov"], 0) + 1
    for p in visitados + pendientes:
        lista.append({"nombre": p["nombre"], "slug": p["slug"], "url": f"pueblos/{p['slug']}/index.html",
                      "lat": p.get("lat"), "lon": p.get("lon"), "prov": p.get("_prov"),
                      "estado": p.get("estado", "visitado"),
                      "fecha": fecha_corta(p["fechas_visita"][-1]) if p.get("fechas_visita") else ""})
    return {"prov": prov, "pend": pend, "pueblos": lista}


def _indice(pueblos: list, cfg, pendientes=()) -> str:
    pendientes = list(pendientes)
    por_com = {}
    for p in pueblos:
        por_com.setdefault(p["comunidad"] or "Sin clasificar", {}).setdefault(
            p["provincia"] or p["comunidad"] or "Sin provincia", []).append(p)
    prov_visitadas = {p["_prov"] for p in pueblos if p.get("_prov")}
    total_prov = len(mapa.provincias())
    comunidades = sorted(por_com, key=_orden_comunidad)

    chips = ['<button data-c="" aria-pressed="true">Todas</button>'] + [
        f'<button data-c="{e(c)}" aria-pressed="false">{e(c)}</button>' for c in comunidades]

    secciones = []
    for c in comunidades:
        provs = por_com[c]
        total = sum(len(v) for v in provs.values())
        bloques = []
        for prov in sorted(provs, key=normalizar):
            fichas = "".join(_ficha(p) for p in sorted(provs[prov], key=lambda x: normalizar(x["nombre"])))
            redundante = len(provs) == 1 and normalizar(prov) in normalizar(c)
            titulo = "" if redundante else f"<h3>{e(prov)}</h3>"
            bloques.append(f'<div class="provincia">{titulo}<div class="rejilla">{fichas}</div></div>')
        secciones.append(
            f'<section class="comunidad" id="{slugify(c)}" data-comunidad="{e(c)}">'
            f'<h2>{e(c)} <small>{total} {"pueblo" if total == 1 else "pueblos"}</small></h2>'
            f'{"".join(bloques)}</section>')

    porcentaje = round(100 * len(prov_visitadas) / total_prov) if total_prov else 0
    datos = json.dumps(_datos_mapa(pueblos, pendientes), ensure_ascii=False).replace("</", "<\\/")
    hay_pend = bool(pendientes)
    seccion_mapa = f"""
<section class="mapa-sec envoltorio" id="mapa">
  <div class="mapa-cab">
    <div><h2>Mi mapa de España</h2>
      <p>Cada provincia se destapa con una foto cuando la visito.</p></div>
    <div class="progreso"><div class="barra"><i data-w="{porcentaje}%"></i></div>
      <small>{len(prov_visitadas)} de {total_prov} provincias destapadas · {porcentaje}%</small></div>
  </div>
  <div class="mapa-marco">
    <div class="mapa-pie">
      <span><i class="muestra m-vis"></i>Visitado</span>
      {'<span><i class="muestra m-pen"></i>Por visitar</span>' if hay_pend else ''}
      <span><i class="muestra m-tap"></i>Sin destapar</span>
      {'<label><input type="checkbox" id="ver-pendientes" checked> Mostrar lo que me queda</label>' if hay_pend else ''}
    </div>
    <div class="panel-prov" aria-live="polite"></div>
  </div>
  <script type="application/json" id="datos-mapa">{datos}</script>
</section>"""

    seccion_pend = ""
    if pendientes:
        fichas = "".join(_ficha(p) for p in sorted(pendientes, key=lambda x: normalizar(x["nombre"])))
        seccion_pend = (f'<section class="pendientes" id="por-visitar"><h2>Próximos destinos</h2>'
                        f'<p>{len(pendientes)} {"pueblo" if len(pendientes) == 1 else "pueblos"} en mi lista de pendientes.</p>'
                        f'<div class="rejilla">{fichas}</div></section>')

    cuerpo = f"""
<header class="cabecera con-dibujo"><div class="envoltorio">
  <div class="sello">Cuaderno de viaje</div>
  <h1>{e(cfg.get('titulo_web'))}</h1>
  <p>{e(cfg.get('subtitulo_web'))}</p>
  <div class="cifras">
    <div>{len(pueblos)}<span>{'pueblo' if len(pueblos) == 1 else 'pueblos'}</span></div>
    <div>{len(prov_visitadas)}<span>de {total_prov} provincias</span></div>
    <div>{len(por_com)}<span>{'comunidad' if len(por_com) == 1 else 'comunidades'}</span></div>
    {f'<div>{len(pendientes)}<span>por visitar</span></div>' if pendientes else ''}
  </div>
</div>
  <div class="paisaje" aria-hidden="true"><svg viewBox="0 0 1440 300" preserveAspectRatio="xMidYMax meet">
    <g class="estrellas"><circle cx="140" cy="40" r="1.6"/><circle cx="260" cy="90" r="1.2"/><circle cx="420" cy="30" r="1.4"/><circle cx="610" cy="60" r="1.1"/>
      <circle cx="760" cy="24" r="1.6"/><circle cx="930" cy="80" r="1.2"/><circle cx="1010" cy="34" r="1.4"/><circle cx="1290" cy="54" r="1.6"/><circle cx="1380" cy="110" r="1.1"/></g>
    <circle class="astro" cx="1140" cy="70" r="46"/>
    <g class="nubes"><ellipse cx="320" cy="60" rx="70" ry="14"/><ellipse cx="380" cy="50" rx="50" ry="12"/><ellipse cx="900" cy="40" rx="60" ry="11"/></g>
    <path class="colina1" d="M0 190 C180 120 300 150 460 120 C620 90 760 150 900 118 C1060 82 1220 130 1440 100 V300 H0Z"/>
    <path class="colina2" d="M0 220 C200 170 380 200 560 175 C760 148 920 205 1100 178 C1260 155 1360 185 1440 170 V300 H0Z"/>
    <g transform="translate(560 120)">
      <rect class="pared" x="120" y="20" width="34" height="110"/><path class="tejado" d="M114 22 L137 -14 L160 22Z"/>
      <rect class="campana" x="131" y="34" width="12" height="16" rx="6"/>
      <rect class="pared2" x="154" y="70" width="90" height="60"/><path class="tejado" d="M150 72 L199 40 L248 72Z"/>
      <rect class="puerta" x="190" y="96" width="16" height="34" rx="8"/>
      <rect class="pared" x="0" y="80" width="70" height="50"/><path class="tejado2" d="M-6 82 L35 52 L76 82Z"/>
      <rect class="ventana" x="12" y="96" width="12" height="14"/><rect class="ventana" x="44" y="96" width="12" height="14"/>
      <rect class="pared2" x="62" y="96" width="58" height="34"/><path class="tejado3" d="M58 98 L91 74 L124 98Z"/>
      <rect class="pared" x="250" y="88" width="64" height="42"/><path class="tejado2" d="M244 90 L282 64 L320 90Z"/>
      <rect class="ventana" x="264" y="102" width="11" height="13"/><rect class="ventana" x="290" y="102" width="11" height="13"/>
      <rect class="pared2" x="318" y="100" width="48" height="30"/><path class="tejado3" d="M314 102 L342 82 L370 102Z"/>
      <rect class="ventana" x="336" y="110" width="10" height="11"/>
      <rect class="pared2" x="-70" y="104" width="66" height="26"/><path class="tejado3" d="M-74 106 L-37 86 L0 106Z"/>
      <path class="arbol" d="M392 130 C380 90 388 60 396 40 C404 60 412 90 400 130Z"/>
      <path class="arbol" d="M-96 130 C-106 98 -100 74 -92 58 C-84 74 -78 98 -88 130Z"/>
    </g>
    <path class="colina3" d="M0 260 C240 225 420 262 640 238 C860 214 1040 262 1240 236 C1330 225 1400 232 1440 228 V300 H0Z"/>
    <path class="camino" d="M700 300 C720 270 690 255 740 238"/>
    <path class="suelo" d="M0 300 V285 C300 270 600 292 900 280 C1150 270 1300 288 1440 282 V300Z"/>
  </svg></div>
</header>
{seccion_mapa}
<nav class="filtros" aria-label="Filtros"><div class="envoltorio">
  <input id="buscar" type="search" placeholder="Buscar un pueblo, provincia…" aria-label="Buscar">
  <div class="chips">{''.join(chips)}</div>
</div></nav>
<main class="envoltorio">
{''.join(secciones) or '<p class="vacio">Todavía no hay pueblos visitados.</p>'}
<p class="vacio" id="nada" hidden>No hay pueblos que coincidan.</p>
{seccion_pend}
</main>
{_pie(cfg)}"""
    return _pagina(cfg.get("titulo_web"), cuerpo, "", cfg.get("subtitulo_web"), JS_INDICE + JS_MAPA,
                   scripts=("js/d3.min.js", "js/d3-composite-projections.min.js", "js/provincias.js"))


# ---------------------------------------------------------------------------- pueblo
def _pagina_pueblo(p: dict, anterior, siguiente, cfg) -> str:
    w = p.get("wiki") or {}
    lugar = " · ".join(x for x in (p["provincia"], p["comunidad"]) if x and x != p["nombre"])
    if p["provincia"] == p["comunidad"]:
        lugar = p["comunidad"]
    visitas = p.get("fechas_visita") or []
    if len(visitas) == 1:
        txt_visitas = f"Visitado {con_articulo(visitas[0])}"
    elif visitas:
        txt_visitas = f"{len(visitas)} visitas · la última {con_articulo(visitas[-1])}"
    else:
        txt_visitas = "Visitado"
    if p.get("estado") == "pendiente":
        txt_visitas = ""
    volver = (f'../../index.html#por-visitar' if p.get("estado") == "pendiente"
              else f'../../index.html#{slugify(p["comunidad"] or "Sin clasificar")}')

    if p.get("portada"):
        heroe = (f'<header class="heroe"><img src="fotos/{e(p["portada"])}" alt="{e(p["nombre"])}">')
    else:
        heroe = '<header class="heroe sin-foto">'
    portada = next((f for f in p.get("fotos", []) if f["archivo"] == p.get("portada")), None)
    credito_portada = (f'<div class="credito-heroe">{credito_html(portada)}</div>'
                       if portada and portada.get("credito") else "")
    heroe += (f'<a class="volver" href="{volver}">← Todos los pueblos</a><div class="envoltorio">'
              f'<div class="lugar">{e(lugar)}</div><h1>{e(p["nombre"])}</h1>'
              f'<div class="visitas">{e(txt_visitas)}</div>'
              f'{"<span class=etiqueta-pend>Por visitar</span>" if p.get("estado") == "pendiente" else ""}'
              f'</div>{credito_portada}</header>')

    principal = []
    if p.get("notas", "").strip():
        principal.append(f'<section class="notas"><h2>Mis notas</h2>{parrafos(p["notas"])}</section>')
    if p.get("texto_ia", "").strip():
        principal.append(f'<section><h2>Sobre {e(p["nombre"])}</h2>{parrafos(p["texto_ia"])}'
                         f'<p class="nota-ia">Texto redactado con ayuda de IA a partir de Wikipedia.</p></section>')
    if w.get("extracto"):
        fuente = (f'<p class="fuente">Fuente: <a href="{e(w.get("url"))}">«{e(w.get("titulo"))}» en Wikipedia</a> '
                  f'(CC BY-SA 4.0)</p>') if w.get("url") else ""
        principal.append(f'<section class="wiki"><h2>Según Wikipedia</h2>{parrafos(w["extracto"])}{fuente}</section>')
    if w.get("que_ver"):
        tarjetas = []
        for lugar in w["que_ver"]:
            img = ""
            if lugar.get("imagen"):
                c = lugar.get("credito") or {}
                img = (f'<img src="{e(lugar["imagen"])}" alt="" loading="lazy">'
                       f'<small class="credito">Foto: {e(c.get("autor"))} · {e(c.get("licencia"))}</small>')
            tarjetas.append(f'<a class="lugar{" sin-img" if not img else ""}" href="{e(lugar.get("url"))}" target="_blank" rel="noopener">'
                            f'{img}<b>{e(lugar["nombre"])}</b></a>')
        principal.append(f'<section class="que-ver"><h2>Qué ver</h2><div class="lugares">{"".join(tarjetas)}</div>'
                         '<p class="fuente">Lugares de interés de Wikidata; fotos de Wikimedia Commons.</p></section>')
    if w.get("secciones"):
        iconos = {"historia": "📜", "patrimonio": "🏛", "fiestas": "🎉", "gastronomia": "🍲", "cultura": "🎭",
                  "leyendas": "🗝", "naturaleza": "🌿", "personajes": "👤"}
        bloques = "".join(
            f'<details><summary><span>{iconos.get(sec.get("clave"), "•")}</span> {e(sec["titulo"])}</summary>'
            f'{parrafos(sec["texto"])}</details>' for sec in w["secciones"])
        fuente = f' <a href="{e(w.get("url"))}">Artículo completo en Wikipedia</a> (CC BY-SA 4.0).' if w.get("url") else ""
        principal.append(f'<section class="saber-mas"><h2>Para saber más</h2>{bloques}'
                         f'<p class="fuente">Fragmentos de Wikipedia.{fuente}</p></section>')
    if not principal:
        principal.append('<section><p class="wiki">Todavía no hay texto sobre este pueblo.</p></section>')

    filas = []
    if p["provincia"]:
        filas.append(("Provincia", p["provincia"]))
    if p["comunidad"] and p["comunidad"] != p["provincia"]:
        filas.append(("Comunidad", p["comunidad"]))
    if w.get("poblacion"):
        anio = f" ({w['poblacion_anio']})" if w.get("poblacion_anio") else ""
        filas.append(("Población", f"{numero(w['poblacion'])} hab.{anio}"))
    if w.get("altitud") is not None and w.get("altitud") != "":
        filas.append(("Altitud", f"{numero(w['altitud'])} m"))
    if w.get("superficie"):
        filas.append(("Superficie", f"{str(w['superficie']).replace('.', ',')} km²"))
    if w.get("gentilicio"):
        filas.append(("Gentilicio", w["gentilicio"]))
    if w.get("patron"):
        filas.append(("Patrón", w["patron"]))
    if visitas:
        filas.append(("Visitas", str(len(visitas))))
    dl = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in filas)
    enlaces = []
    if p.get("lat") is not None:
        enlaces.append(f'<a href="https://www.openstreetmap.org/?mlat={p["lat"]}&mlon={p["lon"]}#map=14/{p["lat"]}/{p["lon"]}">Ver en el mapa</a>')
    if w.get("web"):
        enlaces.append(f'<a href="{e(w["web"])}">Web oficial</a>')
    if w.get("url"):
        enlaces.append(f'<a href="{e(w["url"])}">Artículo en Wikipedia</a>')
    escudo = f'<img class="escudo" src="{e(w["escudo"])}" alt="Escudo de {e(p["nombre"])}" loading="lazy">' if w.get("escudo") else ""
    aside = (f'<aside class="datos">{escudo}<dl>{dl}</dl>'
             f'<div class="enlaces">{"".join(enlaces)}</div></aside>')

    galeria = ""
    if p.get("fotos"):
        items = []
        for f in p["fotos"]:
            pie = f.get("pie") or (fecha_larga(f["fecha"]) if f.get("fecha") else "")
            if f.get("credito"):
                pie = " · ".join(x for x in (f.get("pie"), credito_texto(f)) if x)
            cap = f"<figcaption>{e(f['pie'])}</figcaption>" if f.get("pie") else ""
            if f.get("credito"):
                cap = (f"<figcaption>{e(f['pie']) + '<br>' if f.get('pie') else ''}"
                       f"<span class=\"credito\">{credito_html(f)}</span></figcaption>")
            items.append(f'<figure><a class="ampliar" href="fotos/{e(f["archivo"])}" data-pie="{e(pie)}">'
                         f'<img src="mini/{e(f["archivo"])}" alt="{e(f.get("pie") or p["nombre"])}" loading="lazy"></a>'
                         f'{cap}</figure>')
        galeria = (f'<section class="galeria envoltorio"><h2>Fotos <small style="font:500 15px var(--f-texto);color:var(--tinta-2)">'
                   f'{len(p["fotos"])}</small></h2><div class="mosaico">{"".join(items)}</div></section>'
                   '<div class="visor" role="dialog" aria-label="Foto"><button class="cerrar" aria-label="Cerrar">✕</button>'
                   '<button class="ant" aria-label="Anterior">‹</button><img alt=""><button class="sig" aria-label="Siguiente">›</button><p></p></div>')

    vecinos = '<nav class="vecinos envoltorio">'
    vecinos += (f'<a href="../{e(anterior["slug"])}/index.html"><small>← Anterior</small>{e(anterior["nombre"])}</a>'
                if anterior else "<span></span>")
    vecinos += (f'<a href="../{e(siguiente["slug"])}/index.html" style="text-align:right"><small>Siguiente →</small>{e(siguiente["nombre"])}</a>'
                if siguiente else "<span></span>")
    vecinos += "</nav>"

    cuerpo = (f'{heroe}<div class="cuerpo envoltorio"><div>{"".join(principal)}</div>{aside}</div>'
              f'{galeria}{vecinos}{_pie(cfg)}')
    desc = (w.get("extracto") or p.get("texto_ia") or "")[:160]
    return _pagina(f'{p["nombre"]} · {cfg.get("titulo_web")}', cuerpo, "../../", desc, JS_VISOR)


# ---------------------------------------------------------------------------- generar
def _copiar_si_cambia(origen: Path, destino: Path):
    if destino.exists() and destino.stat().st_size == origen.stat().st_size \
            and destino.stat().st_mtime >= origen.stat().st_mtime:
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)


def generar(almacen: Almacen, cfg, destino: Path, avisar=print) -> int:
    """Crea/actualiza la web en 'destino'. Devuelve el número de pueblos publicados."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    todos = [p for p in almacen.listar() if p.get("publicar", True) and p.get("nombre")]
    if not cfg.get("mostrar_pendientes", True):
        todos = [p for p in todos if p.get("estado") != "pendiente"]
    for p in todos:
        p["_prov"] = mapa.provincia_de(p)
    clave = lambda p: (_orden_comunidad(p["comunidad"] or "Sin clasificar"),  # noqa: E731
                       normalizar(p["provincia"]), normalizar(p["nombre"]))
    visitados = sorted((p for p in todos if p.get("estado") != "pendiente"), key=clave)
    pendientes = sorted((p for p in todos if p.get("estado") == "pendiente"), key=clave)
    pueblos = visitados + pendientes   # para anterior/siguiente: primero los visitados

    js = destino / "js"
    js.mkdir(exist_ok=True)
    for f in ("d3.min.js", "d3-composite-projections.min.js"):
        _copiar_si_cambia(Path(__file__).with_name("js") / f, js / f)
    geo_js = js / "provincias.js"   # como script (no JSON) para que funcione también abriendo el archivo en local
    if not geo_js.exists() or geo_js.stat().st_mtime < mapa.ARCHIVO.stat().st_mtime:
        geo_js.write_text("window.PROVINCIAS_ES=" + mapa.ARCHIVO.read_text(encoding="utf-8") + ";", encoding="utf-8")

    (destino / "estilo.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (destino / ".nojekyll").write_text("", encoding="utf-8")
    (destino / "index.html").write_text(_indice(visitados, cfg, pendientes), encoding="utf-8")

    carpeta_pueblos = destino / "pueblos"
    carpeta_pueblos.mkdir(exist_ok=True)
    for i, p in enumerate(pueblos):
        avisar(f"Generando {p['nombre']}…")
        cp = carpeta_pueblos / p["slug"]
        validas = {f["archivo"] for f in p["fotos"]}
        for sub in ("fotos", "mini"):
            origen_dir = almacen.carpeta_pueblo(p["slug"]) / sub
            destino_dir = cp / sub
            for nombre in validas:
                o = origen_dir / nombre
                if o.exists():
                    _copiar_si_cambia(o, destino_dir / nombre)
            if destino_dir.exists():   # fotos quitadas del pueblo
                for f in destino_dir.iterdir():
                    if f.is_file() and f.name not in validas:
                        f.unlink()
        mismos = visitados if p.get("estado") != "pendiente" else pendientes
        j = mismos.index(p)
        anterior = mismos[j - 1] if j > 0 else None
        siguiente = mismos[j + 1] if j + 1 < len(mismos) else None
        cp.mkdir(parents=True, exist_ok=True)
        (cp / "index.html").write_text(_pagina_pueblo(p, anterior, siguiente, cfg), encoding="utf-8")

    # Pueblos borrados o despublicados: se quitan de la web (solo dentro de sitio/pueblos)
    publicados = {p["slug"] for p in pueblos}
    for c in carpeta_pueblos.iterdir():
        if c.is_dir() and c.name not in publicados and (c / "index.html").exists():
            shutil.rmtree(c)
    return len(pueblos)
