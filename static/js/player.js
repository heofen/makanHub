/* global mini-player */
(function(){
  const audio=document.getElementById('gp-audio');
  const playBtn=document.getElementById('gp-play');
  const pauseBtn=document.getElementById('gp-pause');
  const titleEl=document.getElementById('gp-title');
  const artistEl=document.getElementById('gp-artist');
  const progress=document.getElementById('gp-progress');

  const stored=JSON.parse(localStorage.getItem('gp-state')||'{}');
  if(stored.src){ setTrack(stored,false); }

  playBtn.addEventListener('click',()=>audio.play());
  pauseBtn.addEventListener('click',()=>audio.pause());

  audio.addEventListener('play',toggleBtns);
  audio.addEventListener('pause',toggleBtns);
  function toggleBtns(){
    playBtn.classList.toggle('d-none',!audio.paused?true:false);
    pauseBtn.classList.toggle('d-none',audio.paused?true:false);
  }

  audio.addEventListener('timeupdate',()=>{
    if(audio.duration){ progress.value=(audio.currentTime/audio.duration)*100; }
  });
  progress.addEventListener('input',()=>{
    if(audio.duration){ audio.currentTime=audio.duration*(progress.value/100); }
  });

  window.gpPlay=function({src,title,artist}){
    setTrack({src,title,artist},true);
  };

  function setTrack({src,title,artist},autoplay){
    if(audio.src!==src) audio.src=src;
    titleEl.textContent=title||'Без названия';
    artistEl.textContent=artist||'';
    progress.value=0;
    localStorage.setItem('gp-state',JSON.stringify({src,title,artist}));
    if(autoplay) audio.play();
  }
})(); 