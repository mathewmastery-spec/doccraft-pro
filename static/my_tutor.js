/* My Tutor — compact, action-led tour. It never submits forms or spends credits. */
(function(){
'use strict';
if(window.__docCraftTutorCompact)return;window.__docCraftTutorCompact=true;
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const auth=!!$('#authForm'), key='dcTutorTourV3', activeKey='dcTutorTourActiveV3';
let bubble,hand,target=null,accepted=false,paused=false,stage='invite',observer=null,hideTimer=null;
const reduced=()=>window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function make(tag,attrs,parent){const n=document.createElement(tag);Object.entries(attrs||{}).forEach(([k,v])=>k==='text'?n.textContent=v:n.setAttribute(k,v));if(parent)parent.appendChild(n);return n;}
function clearPoint(){if(target)target.classList.remove('dc-tutor-focus');target=null;if(hand)hand.classList.remove('visible');}
function place(){
 if(!target||!hand||!bubble||paused)return;
 const r=target.getBoundingClientRect();if(!r.width||!r.height)return;
 const x=Math.max(8,Math.min(innerWidth-58,r.left+Math.min(r.width*.55,90)));
 const y=Math.max(8,Math.min(innerHeight-70,r.top-52));
 hand.style.left=x+'px';hand.style.top=y+'px';hand.classList.add('visible');
 const br=bubble.getBoundingClientRect();let bx=Math.max(10,Math.min(innerWidth-br.width-10,x- Math.min(150,br.width*.35)));
 let by=y+64;if(by+br.height>innerHeight-10)by=Math.max(8,y-br.height-12);
 bubble.style.left=bx+'px';bubble.style.top=by+'px';
}
function point(selector,scroll=true){
 clearPoint();const n=typeof selector==='string'?$(selector):selector;
 if(!n||!n.getClientRects().length)return false;
 target=n;n.classList.add('dc-tutor-focus');
 if(scroll)n.scrollIntoView({behavior:reduced()?'auto':'smooth',block:'center',inline:'nearest'});
 requestAnimationFrame(()=>requestAnimationFrame(place));return true;
}
function show(title,message,selector,actions){
 clearTimeout(hideTimer);bubble.hidden=false;
 $('#dcTutorTitle').textContent=title;$('#dcTutorText').textContent=message;
 const row=$('#dcTutorActions');row.replaceChildren();
 (actions||[]).forEach(a=>{const b=make('button',{type:'button',class:a.primary?'dc-tutor-yes':'dc-tutor-later',text:a.label},row);b.addEventListener('click',a.run);});
 if(selector)point(selector);else clearPoint();
}
function collapse(){if(bubble)bubble.hidden=true;clearPoint();}
function anchorInvitation(){
 const logo=$('#dcTutorLauncher');if(!logo||!bubble)return;
 const r=logo.getBoundingClientRect();const w=bubble.getBoundingClientRect().width||290;
 bubble.style.left=Math.max(10,Math.min(innerWidth-w-10,r.left))+'px';
 bubble.style.top=Math.min(innerHeight-145,Math.max(10,r.bottom+10))+'px';
}
function invitation(){
 stage='invite';show('Welcome to DocCraft','New here? May I show you around and explain how everything works?',null,[
 {label:'Show me around',primary:true,run:()=>{accepted=true;sessionStorage.setItem(activeKey,'1');if(auth)authStart();else workspaceStart();}},
 {label:'Maybe later',run:()=>{sessionStorage.setItem(key,'later');collapse();}}
 ]);
 anchorInvitation();
}
function authStart(){
 accepted=true;stage='auth-choice';
 show('Let’s get you started','Choose Sign in if you already have an account, or Create account if this is your first visit.','#loginTab',[]);
}
function workspaceStart(){
 accepted=true;stage='workspace-home';
 show('Welcome to your Document Studio','This is your home base. Start building a document or browse the available tools. I’ll guide you one action at a time.',$('#homeScreen .hero-btns button')||'#tools',[]);
}
function authEvents(){
 document.addEventListener('click',e=>{
  if(!accepted)return;
  if(e.target.closest('#loginTab,#registerTab')){
   const reg=$('#registerTab')?.classList.contains('active');
   setTimeout(()=>show(reg?'Create your account':'Sign in securely',
    reg?'Enter your name, email and password. DocCraft will ask you to verify your email. I will wait while you complete this step.':'Enter your verified account email and password. Your password remains private.',
    reg?'#fullName':'#email',[]),80);
  }
  if(e.target.closest('#resend'))show('Email verification','Use the verification link sent to your inbox. When verification is complete, return here and sign in.','#status',[]);
 });
 const form=$('#authForm');
 form?.addEventListener('submit',()=>{if(accepted){stage='auth-wait';show('Please complete account access','DocCraft is processing your request. I’ll wait here and continue when the account step succeeds.','#status',[]);sessionStorage.setItem(activeKey,'1');}});
 const status=$('#status');
 if(status)new MutationObserver(()=>{
  if(!accepted)return;const t=status.textContent.toLowerCase();
  if(/check your inbox|verification link|account created|verify your email/.test(t))
   show('Verify your email','Open the verification message from DocCraft and follow its link. Then return and sign in.','#status',[]);
  if(t.includes('signed in'))sessionStorage.setItem(activeKey,'1');
 }).observe(status,{childList:true,subtree:true,characterData:true});
}
function observePreview(){
 const sheet=$('#docSheet');if(!sheet)return;
 observer=new MutationObserver(()=>{
  if(!accepted||!sheet.textContent.trim()||stage==='preview')return;
  stage='preview';
  const wm=sheet.classList.contains('preview-watermarked');
  show(wm?'Your watermarked preview':'Your document preview',
   wm?'Review your document here. The watermark indicates that clean export is not unlocked. Use the available actions to see the wallet requirements; I will not bypass them.':'Review the generated document carefully before using the available copy or download actions.',
   '#docSheet',[{label:'Show document actions',primary:true,run:()=>show('Copy and download','These controls use DocCraft’s normal access checks. If clean export is locked, the app will explain the wallet options.','#downloadDocumentBtn',[])}]);
 });
 observer.observe(sheet,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
}
function workspaceEvents(){
 document.addEventListener('click',e=>{
  if(!accepted)return;
  if(e.target.closest('#tools .tool-card,.hero-btns button')){
   setTimeout(()=>show('Choose your document type','Select the document category that matches what you need. Resume, CV and Academic CV are different document types.','#docTypePills',[]),100);
  }
  if(e.target.closest('#docTypePills button,#clTypePills button,#orgTypeGrid button')){
   setTimeout(()=>show('Choose how to create your document','You can work with the AI assistant or complete a structured form. Choose the method that suits your information.','#mainTabs',[]),80);
  }
  if(e.target.closest('#mainTabs button')){
   setTimeout(()=>{
    const form=$('#pane-form')?.classList.contains('active');
    show(form?'Complete the form':'Tell the AI what you need',
     form?'Enter accurate information in the fields. You can move through the form at your own pace.':'Describe the document you want. The assistant can ask questions and refine the details. Review the result before approving generation.',
     form?'#formContent':'#userInput',[]);
   },80);
  }
  if(e.target.closest('#sendBtn'))show('Review the AI conversation','The assistant may ask for missing details. Read its response and use the approval control only when the brief is correct.','#chatApproval',[]);
  if(e.target.closest('#approveGenerateBtn')){
   stage='generating';show('Your document is being prepared','You approved the brief. DocCraft is now generating the document. I’ll explain the preview when it appears.','#docSheet',[]);
  }
  if(e.target.closest('#downloadDocumentBtn,#copyDocumentBtn')){
   show('Document actions','Copy and PDF download are protected by DocCraft’s access checks. If your preview is watermarked, the app will explain what is needed for a clean version.','#downloadDocumentBtn',[]);
  }
  if(e.target.closest('#walletLauncher,#walletNudge')){
   setTimeout(()=>show('Your DocCraft Wallet','Check the account email and available credits here. If you choose to add credits, follow the official checkout. I will never make a payment for you.','#billingPanel',[]),100);
  }
  if(e.target.closest('#workspaceNavTrigger')){
   setTimeout(()=>{
    const care=$$('[onclick*="openWorkspaceCare"]').find(n=>n.offsetParent!==null);
    show('Help and account tools','This menu contains account settings and assistance. DocCraft Care can help while you work.','#workspaceNavMenu',[]);
   },80);
  }
  if(e.target.closest('#careOpen'))show('DocCraft Care','This opens in-workspace AI assistance. Describe the question or document issue you need help with.','#carePopup',[]);
 });
 observePreview();
}
function build(){
 const launcher=$('#dcTutorLauncher');if(!launcher)return;
 launcher.setAttribute('role','button');launcher.setAttribute('tabindex','0');launcher.setAttribute('aria-label','My Tutor — open guided tour');
 bubble=make('aside',{id:'dcTutorBubble','aria-live':'polite','aria-label':'My Tutor guide'},document.body);bubble.hidden=true;
 make('div',{class:'dc-tutor-bubble-kicker',text:'DOCCRAFT GUIDE'},bubble);
 make('button',{class:'dc-tutor-bubble-close',type:'button','aria-label':'Close guide',text:'×'},bubble).addEventListener('click',collapse);
 make('h3',{id:'dcTutorTitle',text:'Welcome'},bubble);make('p',{id:'dcTutorText'},bubble);make('div',{id:'dcTutorActions',class:'dc-tutor-actions'},bubble);
 hand=make('div',{id:'dcTutorMovingHand','aria-hidden':'true',text:'☝️'},document.body);
 const open=()=>{if(!accepted){invitation();return;}paused=false;if(auth)authStart();else workspaceStart();};
 launcher.addEventListener('click',open);
 launcher.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')collapse();});
 window.addEventListener('resize',place);window.addEventListener('scroll',place,{passive:true});
 if(auth){
  authEvents();
  if(sessionStorage.getItem(activeKey)==='1'){accepted=true;authStart();}
  else if(sessionStorage.getItem(key)!=='later')invitation();
 }else{
  const resume=sessionStorage.getItem(activeKey)==='1';
  if(resume){accepted=true;workspaceEvents();workspaceStart();}
  else if(sessionStorage.getItem(key)!=='later')invitation();
  else workspaceEvents();
 }
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build,{once:true});else build();
})();