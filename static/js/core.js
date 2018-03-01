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
});
