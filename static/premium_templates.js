/* Additive premium CV gallery. Existing document and billing flows remain authoritative. */
(function(){
  'use strict';
  const ids=['premium-executive','premium-aurora','premium-creative','premium-ats'];
  const labels={
    'premium-executive':'Executive Heritage',
    'premium-aurora':'Aurora Professional',
    'premium-creative':'Creative Portfolio',
    'premium-ats':'ATS Clean'
  };
  let photoData='';
  function mount(){
    const picker=document.getElementById('templateSelect');
    const bar=document.querySelector('.preview-bar');
    if(!picker||!bar||document.getElementById('premiumTemplateGallery')) return;
    let group=picker.querySelector('optgroup[data-premium-options]');
    if(!group){group=document.createElement('optgroup');group.label='Premium designs';group.dataset.premiumOptions='1';picker.appendChild(group);}
    ids.forEach(id=>{if(!picker.querySelector('option[value="'+id+'"]')){const o=document.createElement('option');o.value=id;o.textContent=labels[id];group.appendChild(o);}});
    const gallery=document.createElement('details');
    gallery.id='premiumTemplateGallery';
    gallery.className='premium-gallery';
    gallery.innerHTML='<summary>✦ Premium CV designs</summary><div class="premium-gallery-panel"><p>Choose a new layout. Your original styles remain available above.</p><div class="premium-gallery-grid">'+ids.map((id)=>'<button type="button" class="premium-design-card" data-template="'+id+'"><span class="premium-swatch '+id+'"></span><strong>'+labels[id]+'</strong><small>'+({ 'premium-executive':'Refined and formal','premium-aurora':'Modern colour sidebar','premium-creative':'Expressive portfolio style','premium-ats':'Simple, ATS-friendly layout'}[id])+'</small></button>').join('')+'</div><label class="premium-photo-label">Optional profile photo <input id="premiumProfilePhoto" type="file" accept="image/jpeg,image/png,image/webp"></label><button type="button" id="premiumRemovePhoto" class="premium-remove-photo">Remove photo</button><small class="premium-photo-note">Photo stays in this browser session and is not uploaded with your document.</small></div>';
    bar.appendChild(gallery);
    gallery.querySelectorAll('[data-template]').forEach(btn=>btn.addEventListener('click',async()=>{
      if(typeof window.setTemplate==='function'){await window.setTemplate(btn.dataset.template,picker);gallery.open=false;}
    }));
    gallery.querySelector('#premiumProfilePhoto').addEventListener('change',event=>{
      const file=event.target.files&&event.target.files[0];if(!file)return;
      if(!/^image\/(jpeg|png|webp)$/.test(file.type)||file.size>2*1024*1024){event.target.value='';if(typeof showToast==='function')showToast('Choose a JPG, PNG or WebP image up to 2 MB.');return;}
      const reader=new FileReader();reader.onload=()=>{photoData=String(reader.result||'');applyPhoto();};reader.readAsDataURL(file);
    });
    gallery.querySelector('#premiumRemovePhoto').addEventListener('click',()=>{photoData='';const input=gallery.querySelector('#premiumProfilePhoto');if(input)input.value='';document.querySelectorAll('#docSheet .premium-profile-photo').forEach(img=>img.remove());});
    const style=document.createElement('style');
    style.textContent='.premium-gallery{margin-left:10px;position:relative;font-size:12px;color:var(--text,#253047)}.premium-gallery summary{cursor:pointer;font-weight:700;color:#7543a6;padding:7px 10px;border:1px solid rgba(117,67,166,.3);border-radius:9px;list-style:none}.premium-gallery-panel{position:absolute;z-index:30;right:0;top:38px;width:min(390px,88vw);padding:14px;background:#fff;color:#243047;border:1px solid #e2d8ee;border-radius:14px;box-shadow:0 12px 34px rgba(25,20,40,.18)}.premium-gallery-panel p{margin:0 0 10px;color:#596579}.premium-gallery-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.premium-design-card{display:flex;flex-direction:column;gap:5px;text-align:left;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:9px;color:#243047;cursor:pointer}.premium-design-card:hover{border-color:#8b5bb6;background:#faf7ff}.premium-design-card small,.premium-photo-note{color:#687386;font-size:10px}.premium-swatch{height:36px;border-radius:6px;background:linear-gradient(90deg,#183b56 0 28%,#fff 28%)}.premium-swatch.premium-aurora{background:linear-gradient(90deg,#176b72 0 34%,#eaf6f5 34%)}.premium-swatch.premium-creative{background:linear-gradient(90deg,#7543a6 0 34%,#f1eafa 34%)}.premium-swatch.premium-ats{background:linear-gradient(180deg,#243b53 0 20%,#fff 20%)}.premium-photo-label{display:block;margin-top:12px;font-weight:600}.premium-photo-label input{display:block;max-width:100%;margin-top:6px;font-weight:400}.premium-remove-photo{margin-top:7px;border:0;background:transparent;color:#7543a6;cursor:pointer;padding:3px}.premium-photo-note{display:block;margin-top:5px}.premium-gallery[open] summary{background:#f7f1fc}@media(max-width:640px){.premium-gallery-panel{right:-8px}.premium-gallery{margin-left:4px}}';
    document.head.appendChild(style);
  }
  function applyPhoto(){
    const sheet=document.getElementById('docSheet');if(!sheet)return;
    sheet.querySelectorAll('.premium-profile-photo').forEach(img=>img.remove());
    if(!photoData)return;
    const target=sheet.querySelector('.tpl-classic .classic-head,.tpl-modern .modern-left');
    if(!target)return;
    const img=document.createElement('img');img.className='premium-profile-photo';img.alt='Profile photo';img.src=photoData;target.insertBefore(img,target.firstChild);
  }
  function observe(){
    const sheet=document.getElementById('docSheet');if(!sheet)return;
    new MutationObserver(()=>applyPhoto()).observe(sheet,{childList:true,subtree:true});
    applyPhoto();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{mount();observe();});else{mount();observe();}
})();
