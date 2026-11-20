/* My Tutor — opt-in tour; deliberately does not invoke DocCraft actions */
(function(){
  'use strict';
  if(window.__docCraftTutorLoaded)return;
  window.__docCraftTutorLoaded=true;
  const steps=[
    {selector:'#homeScreen .hero',title:'Welcome to DocCraft Pro',body:'This is your Document Studio. Start here to create professional documents, refine your content and prepare it for use.'},
    {selector:'#tools',title:'Choose what you want to create',body:'Explore the available document tools. Select the type that matches your goal, such as a resume, CV, cover letter or portfolio.'},
    {selector:'.workspace-switcher',title:'Move between workspaces',body:'Your workspaces keep different DocCraft experiences organised. You can switch spaces here whenever you need to.'},
    {selector:'#careOpen',title:'Get help while you work',body:'DocCraft Care is available inside your document workspace when you need guidance or help improving your content.'}
  ];
  let index=-1,active=null;
  const make=(tag,attrs,parent)=>{const el=document.createElement(tag);Object.keys(attrs||{}).forEach(k=>{if(k==='text')el.textContent=attrs[k];else el.setAttribute(k,attrs[k]);});if(parent)parent.appendChild(el);return el;};
  function build(){
    if(document.getElementById('dcTutorLauncher'))return;
    const launcher=make('button',{id:'dcTutorLauncher',type:'button','aria-controls':'dcTutorPanel','aria-expanded':'false',text:'☝ My Tutor'},document.body);
    const panel=make('section',{id:'dcTutorPanel',role:'dialog','aria-modal':'false','aria-label':'My Tutor guided tour',hidden:''},document.body);
    const top=make('div',{class:'dc-tutor-top'},panel);
    make('span',{class:'dc-tutor-brand',text:'DOC CRAFT  •  MY TUTOR'},top);
    const close=make('button',{class:'dc-tutor-close',type:'button','aria-label':'Close tutor',text:'×'},top);
    const title=make('h2',{id:'dcTutorTitle',text:'Let’s take a quick tour'},panel);
    const body=make('p',{id:'dcTutorBody',text:'I’ll point out the main areas of DocCraft and explain what each one does. You stay in control throughout.'},panel);
    const progress=make('div',{class:'dc-tutor-progress','aria-hidden':'true'},panel);
    make('span',{},progress);
    const actions=make('div',{class:'dc-tutor-actions'},panel);
    const skip=make('button',{class:'dc-tutor-secondary',type:'button',text:'Skip tour'},actions);
    const count=make('span',{class:'dc-tutor-stepcount',text:'Optional guide'},actions);
    const back=make('button',{class:'dc-tutor-secondary',type:'button',text:'Back'},actions);back.hidden=true;
    const next=make('button',{class:'dc-tutor-primary',type:'button',text:'Start tour'},actions);
    const pointer=make('div',{id:'dcTutorPointer','aria-hidden':'true',text:'☝️'},document.body);
    launcher.addEventListener('click',()=>{panel.hidden=false;launcher.setAttribute('aria-expanded','true');title.textContent='Let’s take a quick tour';body.textContent='I’ll point out the main areas of DocCraft and explain what each one does. You stay in control throughout.';progress.firstChild.style.width='0';count.textContent='Optional guide';back.hidden=true;next.textContent='Start tour';skip.hidden=false;index=-1;clearTarget();});
    close.addEventListener('click',closeTour);
    skip.addEventListener('click',closeTour);
    next.addEventListener('click',()=>{if(index<0){index=0;showStep();}else if(index<steps.length-1){index++;showStep();}else{closeTour();}});
    back.addEventListener('click',()=>{if(index>0){index--;showStep();}});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)closeTour();});
    function clearTarget(){if(active)active.classList.remove('dc-tutor-target');active=null;pointer.classList.remove('dc-visible');}
    function closeTour(){clearTarget();panel.hidden=true;launcher.setAttribute('aria-expanded','false');index=-1;}
    function showStep(){
      clearTarget();
      const step=steps[index],candidate=document.querySelector(step.selector),target=candidate&&candidate.getClientRects().length?candidate:null;
      title.textContent=step.title;body.textContent=step.body;
      progress.firstChild.style.width=((index+1)/steps.length*100)+'%';
      count.textContent='Step '+(index+1)+' of '+steps.length;
      back.hidden=index===0;next.textContent=index===steps.length-1?'Finish':'Next';skip.hidden=false;
      if(target){
        active=target;target.classList.add('dc-tutor-target');
        target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});
        window.setTimeout(()=>{if(active!==target)return;const r=target.getBoundingClientRect();pointer.style.left=Math.max(8,Math.min(window.innerWidth-42,r.left+Math.min(r.width/2,90)))+'px';pointer.style.top=Math.max(8,Math.min(window.innerHeight-48,r.top-34))+'px';pointer.classList.add('dc-visible');},220);
      }else{body.textContent+=' This area is not currently visible; continue to the next guide step.';}
    }
    window.addEventListener('resize',()=>{if(active&& !panel.hidden){const r=active.getBoundingClientRect();pointer.style.left=Math.max(8,Math.min(window.innerWidth-42,r.left+Math.min(r.width/2,90)))+'px';pointer.style.top=Math.max(8,Math.min(window.innerHeight-48,r.top-34))+'px';}});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build,{once:true});else build();
})();