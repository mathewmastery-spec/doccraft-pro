/* My Tutor — consistent header guide for account access and DocCraft workspace */
(function(){
  'use strict';
  if(window.__docCraftTutorLoaded)return;
  window.__docCraftTutorLoaded=true;
  const isAuth=!!document.getElementById('authForm');
  const authSteps=[
    {selector:'#loginTab',title:'Welcome to DocCraft Pro',body:'This is your secure entry point. If you already have an account, choose Sign in. I’ll show you the steps without entering or changing any of your details.'},
    {selector:'#registerTab',title:'New to DocCraft? Create an account',body:'Choose Create account if this is your first visit. The registration form will ask for the information needed to set up your account.'},
    {selector:'#email',title:'Use your email address',body:'Enter an email address you can access. DocCraft uses email verification to help protect your account.'},
    {selector:'#password',title:'Keep your password private',body:'Enter your password here. Use a strong password and never share it with anyone. The Show button lets you check what you typed.'},
    {selector:'#submit',title:'Continue securely',body:'When your details are ready, choose this button to sign in or create your account. My Tutor will be waiting in the top navigation after you enter DocCraft.'},
    {selector:'.security-note',title:'Your account protection',body:'Email verification helps confirm account ownership, and your wallet access is checked securely by DocCraft.'}
  ];
  const workspaceSteps=[
    {selector:'#homeScreen .hero',title:'Welcome to your Document Studio',body:'This is your starting point after signing in. Here you can begin creating and improving professional documents.'},
    {selector:'#tools',title:'Choose what you want to create',body:'Explore the document tools and select the one that matches your goal, such as a resume, CV, cover letter or portfolio.'},
    {selector:'.workspace-switcher',title:'Move between workspaces',body:'Use these workspace choices to move between your document work and exploration features.'},
    {selector:'#workspaceNavTrigger',title:'Your account and assistance',body:'Open More to find your profile, wallet, settings, DocCraft Care and Help & Support.'},
    {selector:'#careOpen',title:'Get help while you work',body:'DocCraft Care is also available inside your document workspace whenever you need guidance.'}
  ];
  const steps=isAuth?authSteps:workspaceSteps;
  let index=-1,active=null;
  const make=(tag,attrs,parent)=>{const el=document.createElement(tag);Object.keys(attrs||{}).forEach(k=>{if(k==='text')el.textContent=attrs[k];else el.setAttribute(k,attrs[k]);});if(parent)parent.appendChild(el);return el;};
  function build(){
    if(document.getElementById('dcTutorLauncher'))return;
    const host=isAuth?document.querySelector('.topbar'):document.querySelector('.nav-right');
    if(!host)return;
    const launcher=make('button',{id:'dcTutorLauncher',type:'button','aria-controls':'dcTutorPanel','aria-expanded':'false',text:'☝ My Tutor'},host);
    const panel=make('section',{id:'dcTutorPanel',role:'dialog','aria-modal':'false','aria-label':'My Tutor guided tour',hidden:''},document.body);
    const top=make('div',{class:'dc-tutor-top'},panel);
    make('span',{class:'dc-tutor-brand',text:isAuth?'YOUR FIRST STEPS  •  MY TUTOR':'DOCCRAFT PRO  •  MY TUTOR'},top);
    const close=make('button',{class:'dc-tutor-close',type:'button','aria-label':'Close tutor',text:'×'},top);
    const title=make('h2',{id:'dcTutorTitle',text:isAuth?'Welcome! Let me show you how to get started':'Let’s explore DocCraft'},panel);
    const body=make('p',{id:'dcTutorBody',text:isAuth?'I can guide you through signing in or creating your account. You stay in control of every action.':'I’ll point out the main areas of DocCraft and explain what each one does.'},panel);
    const progress=make('div',{class:'dc-tutor-progress','aria-hidden':'true'},panel);
    make('span',{},progress);
    const actions=make('div',{class:'dc-tutor-actions'},panel);
    const skip=make('button',{class:'dc-tutor-secondary',type:'button',text:'Skip tour'},actions);
    const count=make('span',{class:'dc-tutor-stepcount',text:'Optional guide'},actions);
    const back=make('button',{class:'dc-tutor-secondary',type:'button',text:'Back'},actions);back.hidden=true;
    const next=make('button',{class:'dc-tutor-primary',type:'button',text:'Start guide'},actions);
    const pointer=make('div',{id:'dcTutorPointer','aria-hidden':'true',text:'☝️'},document.body);
    launcher.addEventListener('click',()=>{panel.hidden=false;launcher.setAttribute('aria-expanded','true');title.textContent=isAuth?'Welcome! Let me show you how to get started':'Let’s explore DocCraft';body.textContent=isAuth?'I can guide you through signing in or creating your account. You stay in control of every action.':'I’ll point out the main areas of DocCraft and explain what each one does.';progress.firstChild.style.width='0';count.textContent='Optional guide';back.hidden=true;next.textContent='Start guide';skip.hidden=false;index=-1;clearTarget();});
    close.addEventListener('click',closeTour);skip.addEventListener('click',closeTour);
    next.addEventListener('click',()=>{if(index<0){index=0;showStep();}else if(index<steps.length-1){index++;showStep();}else closeTour();});
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
      back.hidden=index===0;next.textContent=index===steps.length-1?'Finish':'Next';
      if(target){active=target;target.classList.add('dc-tutor-target');target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});window.setTimeout(()=>{if(active!==target)return;const r=target.getBoundingClientRect();pointer.style.left=Math.max(8,Math.min(window.innerWidth-42,r.left+Math.min(r.width/2,90)))+'px';pointer.style.top=Math.max(8,Math.min(window.innerHeight-48,r.top-34))+'px';pointer.classList.add('dc-visible');},220);}
      else body.textContent+=' This part is not visible at the moment; continue to the next guide step.';
    }
    window.addEventListener('resize',()=>{if(active&&!panel.hidden){const r=active.getBoundingClientRect();pointer.style.left=Math.max(8,Math.min(window.innerWidth-42,r.left+Math.min(r.width/2,90)))+'px';pointer.style.top=Math.max(8,Math.min(window.innerHeight-48,r.top-34))+'px';}});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build,{once:true});else build();
})();