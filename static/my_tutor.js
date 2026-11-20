/* My Tutor — event-led, contextual product guide. Never triggers paid actions. */
(function () {
  'use strict';
  if (window.__docCraftTutorV2) return;
  window.__docCraftTutorV2 = true;

  const $ = (s, root=document) => root.querySelector(s);
  const isAuth = !!$('#authForm');
  const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  let panel, launcher, pointer, target=null, stage='welcome', paused=false, started=false, observer=null;
  const journeyKey='dcTutorJourneyV2';

  function el(tag, attrs={}, parent) {
    const node=document.createElement(tag);
    Object.entries(attrs).forEach(([k,v]) => {
      if(k==='text') node.textContent=v;
      else if(k==='html') node.innerHTML=v;
      else node.setAttribute(k,v);
    });
    if(parent) parent.appendChild(node);
    return node;
  }
  function clearTarget(){
    if(target) target.classList.remove('dc-tutor-focus');
    target=null;
    if(pointer) pointer.classList.remove('is-visible');
  }
  function placePointer(node){
    if(!node || !pointer || panel.hidden || paused) return;
    const r=node.getBoundingClientRect();
    if(!r.width || !r.height) return;
    const top=Math.max(8,Math.min(innerHeight-62,r.top-43));
    const left=Math.max(8,Math.min(innerWidth-58,r.left+Math.min(r.width*.55,110)));
    pointer.style.top=top+'px'; pointer.style.left=left+'px';
    pointer.classList.add('is-visible');
  }
  function point(selector, scroll=true){
    clearTarget();
    const node=typeof selector==='string' ? $(selector) : selector;
    if(!node || !node.getClientRects().length) return false;
    target=node; node.classList.add('dc-tutor-focus');
    if(scroll) node.scrollIntoView({behavior:reduceMotion()?'auto':'smooth',block:'center',inline:'nearest'});
    setTimeout(()=>{if(target===node)placePointer(node);},reduceMotion()?0:260);
    return true;
  }
  function say(title, message, selector, opts={}){
    clearTarget();
    $('#dcTutorTitle').textContent=title;
    $('#dcTutorBody').textContent=message;
    $('#dcTutorHint').textContent=opts.hint||'I’ll follow your actions and continue when you’re ready.';
    $('#dcTutorProgress').style.width=(opts.progress||0)+'%';
    if(selector) point(selector);
    $('#dcTutorStatus').textContent=opts.status||'GUIDED EXPERIENCE';
  }
  function openPanel(){
    panel.hidden=false; launcher.setAttribute('aria-expanded','true');
    if(isAuth){
      say('Welcome to DocCraft Pro','I’m your personal product guide. I’ll show you how to enter, create a document, understand your watermarked preview, unlock a clean copy and find help. You stay in control.',null,{progress:3,hint:'Choose “Start my tour” and I’ll guide you as you use the real app.'});
      $('#dcTutorPrimary').hidden=false; $('#dcTutorPrimary').textContent='Start my tour';
    } else {
      say('Welcome to your Document Studio','Let’s explore the real workspace together. I’ll respond to what you open and demonstrate the important routes without spending credits or making purchases.', '#homeScreen .hero-title', {progress:12,hint:'You can work normally. I’ll explain each part as you reach it.'});
      $('#dcTutorPrimary').hidden=true;
      started=true;
      observeWorkspace();
    }
  }
  function closePanel(){
    clearTarget(); panel.hidden=true; launcher.setAttribute('aria-expanded','false');
    paused=true;
  }
  function pausePanel(){
    paused=true; clearTarget();
    $('#dcTutorTitle').textContent='Tour paused';
    $('#dcTutorBody').textContent='Take your time. Your document and account remain in your control. Select Resume whenever you want to continue.';
    $('#dcTutorHint').textContent='No progress is lost during this page session.';
    $('#dcTutorPrimary').hidden=false; $('#dcTutorPrimary').textContent='Resume tour';
  }
  function build(){
    const host=isAuth?$('.topbar'):$('.nav-right');
    if(!host) return;
    launcher=$('#dcTutorLauncher');
    if(!launcher){
      launcher=el('button',{id:'dcTutorLauncher',type:'button','aria-controls':'dcTutorPanel','aria-expanded':'false'},host);
    }
    launcher.className='dc-tutor-launcher';
    launcher.innerHTML='<span class="dc-tutor-launch-icon" aria-hidden="true">✦</span><span>My Tutor</span><span class="dc-tutor-live" aria-hidden="true"></span>';
    panel=el('section',{id:'dcTutorPanel',role:'dialog','aria-modal':'false','aria-label':'My Tutor'},document.body);
    panel.hidden=true;
    if(isAuth) panel.classList.add('dc-tutor-auth');
    el('div',{class:'dc-tutor-topline'},panel);
    const top=$('.dc-tutor-topline',panel);
    el('span',{class:'dc-tutor-brand',text:'DOCCRAFT PRO  /  MY TUTOR'},top);
    el('button',{class:'dc-tutor-close',type:'button','aria-label':'Close My Tutor',text:'×'},top).addEventListener('click',closePanel);
    el('div',{class:'dc-tutor-eyebrow',text:'YOUR INTERACTIVE GUIDE'},panel);
    el('h2',{id:'dcTutorTitle',text:'Welcome'},panel);
    el('p',{id:'dcTutorBody'},panel);
    el('div',{class:'dc-tutor-hint',id:'dcTutorHint'},panel);
    el('div',{class:'dc-tutor-progress-track'},panel);
    el('span',{id:'dcTutorProgress'},$('.dc-tutor-progress-track',panel));
    el('div',{class:'dc-tutor-status',id:'dcTutorStatus',text:'GUIDED EXPERIENCE'},panel);
    const actions=el('div',{class:'dc-tutor-actions'},panel);
    el('button',{id:'dcTutorPause',class:'dc-tutor-secondary',type:'button',text:'Pause'},actions).addEventListener('click',pausePanel);
    el('button',{id:'dcTutorPrimary',class:'dc-tutor-primary',type:'button',text:'Start my tour'},actions).addEventListener('click',()=>{
      if(paused){paused=false; if(isAuth) authWelcome(); else workspaceWelcome(); return;}
      if(isAuth) startAuth(); else {started=true;observeWorkspace();workspaceWelcome();}
    });
    pointer=el('div',{id:'dcTutorPointer','aria-hidden':'true'},document.body);
    pointer.innerHTML='<svg viewBox="0 0 64 72" role="presentation"><path d="M27 5c4 0 7 3 7 7v19l5-5c3-3 8-2 10 1 2 3 1 6-1 9l-9 15c-3 5-8 8-14 8h-4c-7 0-12-5-12-12V37c0-4 3-7 7-7 2 0 4 1 5 3V12c0-4 3-7 6-7Z" fill="#f6f8ff" stroke="#3856b8" stroke-width="3" stroke-linejoin="round"/><path d="M29 14v17" stroke="#8ea8ff" stroke-width="3" stroke-linecap="round"/></svg><span class="dc-tutor-pointer-spark">✦</span>';
    launcher.addEventListener('click',()=>{paused=false;openPanel();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)closePanel();});
    window.addEventListener('resize',()=>placePointer(target));
    window.addEventListener('scroll',()=>placePointer(target),{passive:true});
    if(isAuth) authEvents();
    else {
      const resumeJourney=sessionStorage.getItem(journeyKey)==='workspace';
      if(resumeJourney){sessionStorage.removeItem(journeyKey);openPanel();started=true;observeWorkspace();workspaceWelcome();}
    }
  }
  function authWelcome(){
    say('First, choose how to enter','Already have an account? Select Sign in. New here? Select Create account. I’ll follow the option you choose and wait while you complete each step.', '#loginTab',{progress:8,hint:'Touch either tab. The guide will move with you.'});
    $('#dcTutorPrimary').hidden=true;
  }
  function startAuth(){
    started=true;paused=false;sessionStorage.setItem(journeyKey,'auth');
    authWelcome();
  }
  function authEvents(){
    document.addEventListener('click',e=>{
      if(!started||panel.hidden)return;
      if(e.target.closest('#loginTab,#registerTab')){
        setTimeout(()=>{
          const registering=$('#registerTab').classList.contains('active');
          say(registering?'Create your DocCraft account':'Sign in to your account',
            registering?'Enter your name, email and a secure password. After registration, check your inbox for the verification link. I’ll wait while you do that.':'Enter the email and password associated with your verified account. Your password stays private; I never read or store it.',
            registering?'#fullName':'#email',{progress:registering?16:16,hint:'I’ll wait while you enter your details.'});
        },40);
      }
      if(e.target.closest('#reveal')) {
        say('Password visibility','The Show control lets you check your typing. Hide it again before leaving your device.','#password',{progress:23});
      }
      if(e.target.closest('#resend')) {
        say('Email verification','DocCraft can resend the verification email. Open your inbox and follow the secure link, then return here to sign in.','#status',{progress:28,hint:'I’ll wait for you to finish verification and sign in.'});
      }
    });
    $('#authForm')?.addEventListener('submit',()=>{
      if(!started)return;
      const registering=$('#registerTab').classList.contains('active');
      say(registering?'Check your email to verify':'Signing you in','Your account details are being processed by DocCraft. I won’t interrupt this step. If registration succeeds, verify your email before signing in.','#status',{progress:registering?32:36,hint:'Please complete the account step. I’ll continue when the workspace opens.'});
      sessionStorage.setItem(journeyKey,'auth');
    });
    const status=$('#status');
    if(status)new MutationObserver(()=>{
      if(!started||panel.hidden)return;
      const t=status.textContent.toLowerCase();
      if(t.includes('check your inbox')||t.includes('verification link')||t.includes('account created')){
        say('Verification is the next step','Open the verification email sent by DocCraft and use its link. Once your email is verified, return and sign in. I’ll stay available here.','#resend',{progress:34,hint:'This is a waiting point. No need to click through the tutor.'});
      } else if(t.includes('signed in')){
        say('You’re in — opening your studio','Your sign-in succeeded. I’ll continue inside your Document Studio.','#status',{progress:40});
      }
    }).observe(status,{childList:true,subtree:true,characterData:true});
  }
  function workspaceWelcome(){
    say('Your Document Studio','This is your home base. Start with a document tool, or explore the workspace and account menu. I’ll explain each feature when you open it.', '#homeScreen .hero-title',{progress:43,hint:'Choose Start Building or Explore Tools to begin.'});
  }
  function observeWorkspace(){
    if(observer)observer.disconnect();
    const sheet=$('#docSheet');
    if(sheet) observer=new MutationObserver(()=>{
      if(!started||panel.hidden||!sheet.textContent.trim())return;
      const watermarked=sheet.classList.contains('preview-watermarked');
      say(watermarked?'Your watermarked preview is ready':'Your document preview is ready',
        watermarked?'This is your real generated preview. The watermark shows that clean export is not currently unlocked. You can review the document and use the available print/preview route; clean copying and PDF export require wallet access.':'Your document has been generated. Review the content and use the available document actions. Clean export is available when your account has the required access.',
        '#docSheet',{progress:75,hint:'Review the preview. I’ll explain download and wallet access next.'});
      $('#dcTutorPrimary').hidden=false;$('#dcTutorPrimary').textContent='Show download options';
    });
    if(sheet)observer.observe(sheet,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
  }
  function showDownload(){
    say('Preview, download and print','DocCraft keeps the watermarked preview visible when the account has no eligible email or credits. Clean PDF download and copy actions are protected. The tutor will not remove the watermark or spend credits for you.','#downloadDocumentBtn',{progress:82,hint:'Try the available preview/print option. If export is locked, open Wallet to see how to unlock it.'});
    $('#dcTutorPrimary').hidden=false;$('#dcTutorPrimary').textContent='Take me to Wallet';
  }
  function showWallet(){
    const opened=typeof window.openWalletPalette==='function';
    if(opened)window.openWalletPalette();
    say('Your DocCraft Wallet','Your wallet shows the account email and credit balance. Add credits through the official checkout if you choose. Once the required access is confirmed, generate or export a clean document.','#billingPanel',{progress:90,hint:'I will never purchase credits or submit a payment on your behalf.'});
    $('#dcTutorPrimary').hidden=false;$('#dcTutorPrimary').textContent='Show help & support';
  }
  function showHelp(){
    const trigger=$('#workspaceNavTrigger')||$('.workspace-nav-trigger');
    if(trigger)trigger.click();
    const help=[...document.querySelectorAll('button')].find(b=>/help & support/i.test(b.innerText));
    say('Help when you need it','Use Help & Support for guidance beyond this tour. DocCraft Care is also available from inside your document workspace for questions while you work.',help||'#careOpen',{progress:96,hint:'You can return to My Tutor at any time from the header.'});
    $('#dcTutorPrimary').hidden=true;
  }
  document.addEventListener('click',e=>{
    if(!started||panel.hidden||isAuth)return;
    if(e.target.closest('#dcTutorPrimary')){
      if($('#dcTutorPrimary').textContent.includes('download'))showDownload();
      else if($('#dcTutorPrimary').textContent.includes('Wallet'))showWallet();
      else if($('#dcTutorPrimary').textContent.includes('help'))showHelp();
    }
    if(e.target.closest('#walletLauncher,#careProfile')){
      say('Wallet and account','This opens your wallet and account area. Check your balance here and review the available credit options.', '#billingPanel',{progress:90});
    }
    if(e.target.closest('#careOpen')){
      say('DocCraft Care','Ask for help while you work. You can describe the document challenge and get guidance without leaving your workspace.','#carePopup',{progress:98});
    }
    if(e.target.closest('#workspaceNavTrigger,.workspace-nav-trigger')){
      setTimeout(()=>showHelp(),100);
    }
    if(e.target.closest('#tools button,.tools-grid button,.tool-card button')){
      const button=e.target.closest('button');
      say('Choose your document type','You have opened a document tool. Select the document type that matches your purpose, then choose how you want to provide the information.','#docTypePills',{progress:53,hint:'Choose a document type. I’ll follow your selection.'});
    }
    if(e.target.closest('#docTypePills button')){
      say('Choose how to create it','You can describe your goal in the AI conversation or complete the structured form. The form gives you direct control over each detail.','#mainTabs',{progress:59});
    }
    if(e.target.closest('#mainTabs button')){
      const pane=$('#pane-form')?.classList.contains('active')?'#formContent':'#pane-chat';
      say(pane==='#pane-form'?'Complete the form':'Work with the AI assistant',
        pane==='#pane-form'?'Fill in the fields with accurate information. You can add extra tips to guide the result. I’ll wait while you type.':'Describe what you want to create. The assistant can ask questions and refine the brief. Review it, then explicitly approve before generation.',
        pane,{progress:64,hint:'Type at your own pace. I won’t submit or generate anything automatically.'});
    }
    if(e.target.closest('#approveGenerateBtn')){
      say('Your approved document is being prepared','You approved the brief and started generation. I’ll wait for the real result, then explain the preview and available export options.','#docSheet',{progress:70});
    }
    if(e.target.closest('#downloadDocumentBtn,#copyDocumentBtn'))showDownload();
    if(e.target.closest('#walletLauncher'))showWallet();
  });
  document.addEventListener('focusin',e=>{
    if(!started||panel.hidden||isAuth)return;
    if(e.target.closest('#formContent')){
      const field=e.target;
      const label=field.labels?.[0]?.textContent||field.closest('.form-group')?.querySelector('label')?.textContent||field.getAttribute('aria-label')||'this field';
      say('Add your information','You are editing '+label.trim()+'. Use your own accurate details. The form saves your answers in the document workflow; I won’t type private information for you.','#formContent',{progress:66,hint:'I’ll stay out of your way while you write.'});
    }
    if(e.target.closest('#userInput')){
      say('Describe your document','Tell the assistant what you need, who the document is for and any important context. Enter creates a new line; use the send control when you are ready.','#userInput',{progress:66});
    }
  });
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build,{once:true});else build();
})();