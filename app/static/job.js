var job = {};

job.loadDom = function(selector, jobUrl) {
  $.get(jobUrl, function(data) {
    var dom = $.parseHTML(data.dom, keepScripts=true);
    $(selector).html(dom);
    if (data.status != 'ok') {
      setTimeout(
          function(){job.loadDom(selector, jobUrl)},
          500);
    }
  });
}

job.postCleanseOn = function(btnSelector, formSelector) {
	$(document).on('click', btnSelector, function() {
		$(formSelector).submit();
	});
}