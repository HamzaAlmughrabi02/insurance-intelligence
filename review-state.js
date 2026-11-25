// Transient employee interaction state. Never persisted to browser storage.
const reviewUI=(()=>{
 let generation=0,draftScope='';const drafts=new Map();
 const scope=(id,version)=>JSON.stringify([id,version]);
 function context(){return {generation,id:typeof currentId==='undefined'?'':currentId,page:typeof page==='undefined'?'':page,request:typeof v2Request==='undefined'?null:v2Request}}
 function current(origin){const now=context();return origin.generation===now.generation&&origin.id===now.id&&origin.page===now.page&&origin.request===now.request}
 function key(node){return node.id||node.getAttribute?.('onsubmit')||''}
 function edited(event){const input=event.target;if(!input?.closest?.('#detail'))return;const node=input.closest('form')||(input.id?.startsWith('note-')?input:null);if(node){node.dataset.draftDirty='true';node.dataset.draftEdit=String(Number(node.dataset.draftEdit||0)+1)}}
 document.addEventListener?.('input',edited);document.addEventListener?.('change',edited);
 function capture(root){if(!root?.querySelectorAll||!draftScope||root.dataset?.draftScope!==draftScope)return;for(const node of root.querySelectorAll('form,textarea[id^="note-"]')){const name=key(node);if(!name||node.dataset.draftDirty!=='true')continue;const active=document.activeElement,focused=node===active||node.contains?.(active);drafts.set(name,{node,open:node.closest?.('details')?.open,active:focused?active:null,start:focused?active.selectionStart:null,end:focused?active.selectionEnd:null})}}
 function restore(root){if(!root?.querySelectorAll)return;root.dataset.draftScope=draftScope;for(const node of root.querySelectorAll('form,textarea[id^="note-"]')){const saved=drafts.get(key(node));if(!saved||node===saved.node)continue;node.replaceWith(saved.node);if(saved.open){const details=saved.node.closest?.('details');if(details)details.open=true}if(saved.active){saved.active.focus?.({preventScroll:true});try{saved.active.setSelectionRange(saved.start,saved.end)}catch{}}}}
 function useScope(id,version){const next=scope(id,version);if(next!==draftScope){drafts.clear();draftScope=next}}
 function clear(){drafts.clear();draftScope='';generation++}
 function saved(node,edit){if(node&&String(node.dataset.draftEdit||'0')===String(edit||'0')){node.dataset.draftDirty='false';if(drafts.get(key(node))?.node===node)drafts.delete(key(node))}}
 const baseGo=typeof go==='function'?go:null;if(baseGo)go=function(...args){generation++;return baseGo(...args)};
 return {context,current,capture,restore,useScope,clear,saved,navigate:()=>++generation,latest:value=>value===generation};
})();
