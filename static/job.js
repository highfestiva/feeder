var job = {};

job.loadDom = function(selector, jobUrl) {
  $.get(jobUrl, function(data) {
    var dom = $.parseHTML(data.dom);
    $(selector).html(dom);
    if (data.status != 'ok') {
      setTimeout(
          function(){job.loadDom(selector, jobUrl)},
          500);
    }
  });
}
