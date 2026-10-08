const brandToggle=$('#brand-switch-toggle'),brandOptions=$('#brand-options');
$('#brand-switch-toggle small').textContent='点击切换';
function closeBrandOptions(){brandToggle.setAttribute('aria-expanded','false');brandOptions.hidden=true;}
brandToggle.onclick=()=>{const open=brandOptions.hidden;brandOptions.hidden=!open;brandToggle.setAttribute('aria-expanded',String(open));};
document.addEventListener('click',e=>{if(!e.target.closest('.brand-picker'))closeBrandOptions();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!brandOptions.hidden){closeBrandOptions();brandToggle.focus();}});
let brandSwitchBusy=false,brandPublishBusy=false;
const publishOriginal=$('#publish-btn').onclick;
$('#publish-btn').onclick=async()=>{brandPublishBusy=true;try{await publishOriginal();}finally{brandPublishBusy=false;}};
$('#brand-options').onclick=async e=>{
 const target=e.target.closest('[data-brand]');if(!target)return;e.preventDefault();
 if(target.dataset.brand===studioBrand){closeBrandOptions();return;}
 if(brandSwitchBusy)return;
 if(isUploading||isAnalyzing||brandPublishBusy||$('#generate-cover').classList.contains('busy')){toast('正在处理当前内容，请完成后再切换品牌',true);return;}
 if(currentRoute==='settings'){
  const form=$('#settings-form');
  const changed=['brand','content_direction','tone','base_url','vision_model','audio_model','image_model'].some(k=>form.elements[k].value!==(state.settings[k]||''))||!!form.elements.api_key.value;
  if(changed&&!confirm('设置尚未保存，切换品牌将放弃这些修改。继续切换？'))return;
 }
 brandSwitchBusy=true;brandToggle.disabled=true;
 try{
  if(dirty){clearTimeout(savingTimer);++saveSequence;const saved=await api('draft',draft);state.draft=saved.cleared?null:saved;dirty=false;}
  location.assign(target.getAttribute('href')+'#'+currentRoute);
 }catch(err){toast('草稿未保存，暂未切换：'+err.message,true);brandSwitchBusy=false;brandToggle.disabled=false;}
};
