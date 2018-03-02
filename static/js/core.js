$(document).ready(function() {
  $.datetimepicker.setLocale('ru');

  $('.dt-input').each(function () {
    $(this).datetimepicker({
      format: 'd.m.Y H:i',
      value: $(this).val()
    });
  });

  $('.date-input').datetimepicker({
    format: 'd.m.Y',
    timepicker: false
  });

  $('.grouping').click(function () {
    $(this).toggleClass('collapsed').toggleClass('expanded');
    $(this).parents('table').find('tr.detailed[data-rel="' + $(this).data('rel') + '"]').toggleClass('hidden');
  });
});
