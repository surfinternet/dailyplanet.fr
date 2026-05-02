(function () {
  var bar = document.getElementById('progress');
  if (!bar) return;
  window.addEventListener('scroll', function () {
    var scrollTop = window.scrollY;
    var docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) return;
    bar.style.width = Math.min(100, (scrollTop / docHeight) * 100) + '%';
  }, { passive: true });
}());
