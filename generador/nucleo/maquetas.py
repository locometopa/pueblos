"""Maquetas de página completa: cambian el aspecto de toda la web (portada y fichas).

clasica  — la de siempre.
revista  — editorial: cabecera como portada de revista, rejilla con pueblo destacado, capitulares, filetes.
album    — álbum de viaje: papel kraft, polaroids torcidas, cinta adhesiva y letra a mano.
moderna  — tipo app: letra sin remates muy marcada, tarjetas grandes con el nombre sobre la foto, esquinas redondas.
"""

MAQUETAS = {
    "clasica": ("Clásica", "La actual: limpia, con azulejos y bandas de color."),
    "revista": ("Revista", "Como una revista de viajes: portada, gran foto destacada y capitulares."),
    "album": ("Álbum de viaje", "Polaroids torcidas, cinta adhesiva y letra a mano sobre papel."),
    "moderna": ("Moderna", "Tipo app: letra grande, fotos protagonistas y esquinas redondas."),
}

FUENTES = {
    "album": '<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&display=swap" rel="stylesheet">',
    "moderna": '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap" rel="stylesheet">',
}

CSS = """
[hidden]{display:none!important}
.ficha .f-prov{display:none}
/* ======================= REVISTA ======================= */
.m-revista{background-image:none!important}
.m-revista .banda,.m-revista .comunidad:nth-of-type(odd),.m-revista .pendientes{background:none!important;box-shadow:none!important}
.m-revista .cabecera{text-align:center;border-top:6px double var(--tinta);border-bottom:1px solid var(--tinta);padding-top:34px}
.m-revista .cabecera .envoltorio{display:flex;flex-direction:column;align-items:center}
.m-revista .cabecera .marca{justify-content:center}
.m-revista .cabecera .sello{display:flex;align-items:center;gap:14px;color:var(--tinta-2);letter-spacing:.3em}
.m-revista .cabecera .sello::before,.m-revista .cabecera .sello::after{content:"";width:60px;height:1px;background:var(--tinta-2)}
.m-revista .cabecera h1{font-size:clamp(48px,10vw,120px);letter-spacing:-.04em;margin:10px 0 6px}
.m-revista .cabecera p{font-style:italic;max-width:60ch;margin:0 auto}
.m-revista .cifras{justify-content:center;border-top:1px solid var(--linea);border-bottom:1px solid var(--linea);padding:12px 0;margin-top:22px}
.m-revista .paisaje{opacity:.55}
.m-revista .filtros{background:var(--papel);border-bottom:1px solid var(--tinta)}
.m-revista .chips button{border:0;border-radius:0;background:none;text-transform:uppercase;letter-spacing:.12em;font-size:12px;font-weight:600;padding:6px 8px}
.m-revista .chips button[aria-pressed=true]{background:none;color:var(--acento);box-shadow:inset 0 -2px 0 var(--acento)}
.m-revista main{counter-reset:capitulo}
.m-revista .comunidad>h2{display:grid;grid-template-columns:auto 1fr;align-items:end;gap:6px 18px;font-size:clamp(34px,5vw,54px);
  border-top:1px solid var(--tinta);padding-top:14px}
.m-revista .comunidad>h2::before{counter-increment:capitulo;content:counter(capitulo,decimal-leading-zero);grid-row:span 2;
  font:400 clamp(40px,6vw,72px)/1 var(--f-titulo);color:var(--acento);font-style:italic}
.m-revista .comunidad>h2 small{text-transform:uppercase;letter-spacing:.14em;font-size:12px}
.m-revista main.envoltorio{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));column-gap:34px;align-items:start}
.m-revista main>*:not(.comunidad),.m-revista main>.comunidad:is(:has(.ficha ~ .ficha ~ .ficha),:has(.provincia ~ .provincia ~ .provincia),:has(.provincia:has(.ficha ~ .ficha) ~ .provincia),:has(.provincia ~ .provincia:has(.ficha ~ .ficha))){grid-column:1/-1}
.m-revista .comunidad{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:30px 26px;align-items:start}
.m-revista .comunidad>h2{grid-column:1/-1}
.m-revista .comunidad .provincia,.m-revista .comunidad .rejilla{display:contents}
.m-revista .comunidad .provincia h3{display:none}
.m-revista .ficha .f-prov{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--acento-2);font-weight:600}
.m-revista .pendientes .rejilla{grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:30px 26px}
.m-revista .ficha{background:none;box-shadow:none;border-radius:0}
.m-revista .ficha .foto{aspect-ratio:4/5;border-radius:0}
.m-revista .ficha .texto{padding:10px 0 0}
.m-revista .ficha h4{font-size:24px;font-style:italic;font-weight:500}
.m-revista .ficha p{text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:600}
@media (min-width:700px){
  .m-revista .comunidad:is(:has(.ficha ~ .ficha ~ .ficha),:has(.provincia ~ .provincia ~ .provincia),:has(.provincia:has(.ficha ~ .ficha) ~ .provincia),:has(.provincia ~ .provincia:has(.ficha ~ .ficha))) .provincia:first-of-type .ficha:first-child{grid-column:span 2}
  .m-revista .comunidad:is(:has(.ficha ~ .ficha ~ .ficha),:has(.provincia ~ .provincia ~ .provincia),:has(.provincia:has(.ficha ~ .ficha) ~ .provincia),:has(.provincia ~ .provincia:has(.ficha ~ .ficha))) .provincia:first-of-type .ficha:first-child .foto{aspect-ratio:16/10}
  .m-revista .comunidad:is(:has(.ficha ~ .ficha ~ .ficha),:has(.provincia ~ .provincia ~ .provincia),:has(.provincia:has(.ficha ~ .ficha) ~ .provincia),:has(.provincia ~ .provincia:has(.ficha ~ .ficha))) .provincia:first-of-type .ficha:first-child h4{font-size:34px}}
.m-revista section>h2,.m-revista .mapa-cab h2{font-size:clamp(30px,4vw,46px)}
.m-revista .mapa-marco,.m-revista .datos,.m-revista .caja,.m-revista .hito,.m-revista .tarjeta-fiesta,.m-revista .lista-fiestas li{border-radius:0;box-shadow:none;border:1px solid var(--linea)}
.m-revista .heroe h1{font-size:clamp(52px,11vw,130px);font-style:italic;font-weight:500}
.m-revista .cuerpo .wiki>p:first-of-type::first-letter{float:left;font:600 4.4em/.78 var(--f-titulo);margin:8px 10px 0 0;color:var(--acento)}
.m-revista .datos{border-top:4px solid var(--tinta)}
.m-revista footer{border-top:6px double var(--tinta);text-align:center}

/* ======================= ÁLBUM ======================= */
.m-album{--f-mano:"Caveat",cursive;background-color:color-mix(in srgb,var(--papel) 82%,#c8a46e);
  background-image:radial-gradient(color-mix(in srgb,var(--tinta) 9%,transparent) 1px,transparent 1.2px)!important;background-size:14px 14px!important}
.m-album .banda,.m-album .comunidad:nth-of-type(odd),.m-album .pendientes{background:none!important;box-shadow:none!important}
.m-album .cabecera h1,.m-album .comunidad>h2,.m-album section>h2,.m-album .mapa-cab h2,.m-album .heroe h1,.m-album .cuaderno h2{
  font-family:var(--f-mano);font-weight:700;letter-spacing:0}
.m-album .cabecera h1{font-size:clamp(56px,10vw,110px)}
.m-album .cabecera .sello{display:inline-block;background:color-mix(in srgb,var(--acento-2) 45%,transparent);color:var(--tinta);
  padding:6px 16px;transform:rotate(-2deg);letter-spacing:.2em}
.m-album main.envoltorio{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:40px 30px;padding-top:40px;align-items:start}
.m-album main>.comunidad,.m-album main .comunidad .provincia,.m-album main .comunidad .rejilla{display:contents}
.m-album main>*:not(.comunidad){grid-column:1/-1}
.m-album .comunidad .provincia h3{display:none}
.m-album .comunidad>h2{margin:0;align-self:stretch;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;
  font-size:clamp(40px,5vw,54px);line-height:1;padding:24px 14px;transform:rotate(2deg);
  background:color-mix(in srgb,#ffe58a 82%,var(--acento-2));color:#3a3226;box-shadow:0 8px 18px rgba(0,0,0,.15);min-height:170px;align-self:center;width:86%;justify-self:center}
.m-album .comunidad>h2 small{font-family:var(--f-texto);font-size:14px;color:#6b5d48;margin-top:6px}
.m-album .comunidad:nth-of-type(2n)>h2{transform:rotate(-2.5deg);background:color-mix(in srgb,#ffc9b0 85%,var(--acento))}
.m-album .ficha .f-prov{display:block;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#9a8b78}
.m-album .provincia h3{display:inline-flex;border:2px dashed var(--acento-2);border-radius:8px;padding:6px 12px;transform:rotate(1deg)}
.m-album .provincia h3::after{display:none}
.m-album .pendientes .rejilla{gap:34px 28px;padding:6px}
.m-album .ficha{background:#fbf8f1;border-radius:2px;padding:10px 10px 4px;box-shadow:0 8px 20px rgba(0,0,0,.18);transform:rotate(-1.6deg);
  transition:transform .25s}
.m-album .ficha:nth-child(2n){transform:rotate(1.4deg)}
.m-album .ficha:nth-child(3n){transform:rotate(-.6deg)}
.m-album .ficha:hover{transform:rotate(0) scale(1.04);z-index:2}
.m-album .ficha .foto{border-radius:0;aspect-ratio:1}
.m-album .ficha .texto{text-align:center;padding:8px 4px 8px}
.m-album .ficha h4{font:700 28px/1.05 var(--f-mano);color:#2f2a25}
.m-album .ficha p{color:#7a6f63}
.m-album .ficha::before{content:"";position:absolute;top:-10px;left:50%;width:70px;height:20px;transform:translateX(-50%) rotate(-3deg);
  background:color-mix(in srgb,var(--acento-2) 50%,transparent);z-index:2}
.m-album .ficha{position:relative}
.m-album .mapa-marco{border:12px solid #fbf8f1;border-bottom-width:40px;border-radius:2px;box-shadow:0 10px 26px rgba(0,0,0,.2)}
.m-album .heroe{background:transparent}
.m-album .heroe::after{inset:18px}
.m-album .heroe img{inset:18px;width:calc(100% - 36px);height:calc(100% - 36px);border:10px solid #fbf8f1;box-shadow:0 10px 30px rgba(0,0,0,.3)}
.m-album .heroe h1{font-size:clamp(60px,12vw,130px)}
.m-album .galeria figure{background:#fbf8f1;padding:8px 8px 22px;box-shadow:0 6px 16px rgba(0,0,0,.18);transform:rotate(-1deg)}
.m-album .galeria figure:nth-child(2n){transform:rotate(1.2deg)}
.m-album .datos{background:#fbf8f1;color:#2f2a25;border-radius:4px;background-image:repeating-linear-gradient(transparent 0 31px,#d9e3ef 31px 32px)}
@media (prefers-color-scheme:dark){.m-album{background-color:color-mix(in srgb,var(--papel) 90%,#c8a46e)}}

/* ======================= MODERNA ======================= */
.m-moderna{--f-titulo:"Inter",system-ui,"Segoe UI",sans-serif;--f-texto:"Inter",system-ui,"Segoe UI",sans-serif;--radio:22px;background-image:none!important}
.m-moderna .banda,.m-moderna .comunidad:nth-of-type(odd),.m-moderna .pendientes{background:none!important;box-shadow:none!important}
.m-moderna h1,.m-moderna h2,.m-moderna h3,.m-moderna h4{font-weight:800!important;letter-spacing:-.03em}
.m-moderna .cabecera h1{font-size:clamp(44px,8vw,92px);line-height:.95}
.m-moderna .cabecera .sello{display:inline-block;padding:6px 12px;border-radius:99px;background:var(--acento);color:#fff;letter-spacing:.08em}
.m-moderna .cifras>div{background:var(--tarjeta);border-radius:18px;padding:14px 18px;box-shadow:var(--sombra)}
.m-moderna .filtros{background:color-mix(in srgb,var(--papel) 80%,transparent);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)}
.m-moderna .filtros input{border-radius:99px;border:0;background:var(--tarjeta);box-shadow:var(--sombra)}
.m-moderna .chips button{border:0;background:var(--tarjeta);box-shadow:var(--sombra);font-weight:600}
.m-moderna .chips button[aria-pressed=true]{background:var(--tinta);color:var(--papel)}
.m-moderna main.envoltorio{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px;padding-top:28px}
.m-moderna main>.comunidad,.m-moderna main .comunidad .provincia,.m-moderna main .comunidad .rejilla{display:contents}
.m-moderna main>*:not(.comunidad){grid-column:1/-1}
.m-moderna .comunidad .provincia h3{display:none}
.m-moderna .comunidad>h2{margin:0;border-radius:24px;padding:22px;display:flex;flex-direction:column;justify-content:flex-end;
  background:color-mix(in srgb,var(--acento) 12%,var(--papel));color:var(--acento);font-size:clamp(30px,3.4vw,40px);line-height:1;
  min-height:200px;border:2px solid color-mix(in srgb,var(--acento) 30%,transparent)}
.m-moderna .comunidad>h2::before{content:"";width:34px;height:4px;border-radius:4px;background:currentColor;margin-bottom:auto}
.m-moderna .comunidad:nth-of-type(2n)>h2{background:color-mix(in srgb,var(--acento-2) 14%,var(--papel));color:var(--acento-2);
  border-color:color-mix(in srgb,var(--acento-2) 30%,transparent)}
.m-moderna .comunidad>h2 small{color:var(--tinta-2);font-size:14px;font-weight:600;letter-spacing:0;margin-top:8px}
.m-moderna .ficha .f-prov{display:block;font-size:12px;font-weight:600;color:rgba(255,255,255,.8);text-transform:uppercase;letter-spacing:.06em}
.m-moderna .pendientes .rejilla{grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}
.m-moderna .ficha{position:relative;border-radius:24px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.12)}
.m-moderna .ficha .foto{aspect-ratio:3/4}
.m-moderna .ficha .texto{position:absolute;left:0;right:0;bottom:0;padding:40px 16px 14px;color:#fff;
  background:linear-gradient(transparent,rgba(0,0,0,.72))}
.m-moderna .ficha h4{font-size:24px;color:#fff}
.m-moderna .ficha p{color:rgba(255,255,255,.85)}
.m-moderna .ficha.pend .texto{background:linear-gradient(transparent,color-mix(in srgb,var(--pendiente) 85%,#000))}
.m-moderna .mapa-marco{border-radius:28px}
.m-moderna .heroe{margin:12px;border-radius:30px;overflow:hidden;min-height:min(62vh,560px)}
.m-moderna .heroe h1{font-size:clamp(48px,10vw,110px);line-height:.92}
.m-moderna .datos,.m-moderna .caja{border-radius:24px}
.m-moderna .hito,.m-moderna .tarjeta-fiesta,.m-moderna .lista-fiestas li{border-radius:18px}
.m-moderna .galeria .mosaico img{border-radius:16px}
"""

CSS += """
@media (max-width:600px){
  .m-moderna main.envoltorio,.m-album main.envoltorio{grid-template-columns:1fr 1fr;gap:14px}
  .m-moderna .comunidad>h2,.m-album .comunidad>h2{grid-column:1/-1;min-height:0;flex-direction:row;align-items:baseline;
    justify-content:flex-start;gap:10px;padding:12px 16px;width:auto;font-size:30px}
  .m-moderna .comunidad>h2::before{display:none}
  .m-moderna .ficha h4{font-size:18px}.m-moderna .ficha .texto{padding:30px 12px 10px}
  .m-album .ficha h4{font-size:22px}.m-album .ficha{padding:7px 7px 2px}
  .m-album .comunidad>h2{transform:rotate(-1deg)}
}
"""
