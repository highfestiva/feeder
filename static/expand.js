$(document).on('click', '.expand-click', function(event) {
	event.stopPropagation();
	var blob = $(this);
	blob.removeClass('jelly_animate');
	blob.addClass('jelly_animate');
	blob.children('.expand-item').toggleClass('hidden');
	var path = blob.children('.expand-path');
	if (path.length) {
		path.removeClass('expand-path');
		var url = path.text();
		path.text('Loading...');
		$.ajax(url).done(function(data) {
			path.html(data);
		});
	}
});
