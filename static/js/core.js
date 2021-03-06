$(document).ready(function() {
  $.datetimepicker.setLocale('ru');

  $('.dt-input').each(function () {
    $(this).datetimepicker({
      format: 'd.m.Y H:i',
      value: $(this).val(),
      lang:'ru',
      dayOfWeekStart: 1
    });
  });

  $('.date-input').datetimepicker({
    format: 'd.m.Y',
    timepicker: false,
    lang:'ru',
    dayOfWeekStart: 1
  });

  $('select.select-searchable').select2();
  $('.grouping').click(function () {
    $(this).toggleClass('collapsed').toggleClass('expanded');
    $(this).parents('table').find('tr.detailed[data-rel="' + $(this).data('rel') + '"]').toggleClass('hidden');
  });
});
