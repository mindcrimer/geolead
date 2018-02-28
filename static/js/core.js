$(document).ready(function() {
  $.datetimepicker.setLocale('ru');

  $('.dt-input').datetimepicker({
    startDate: '+1971/05/01',
    format: 'd.m.Y H:i'
  });

  $('.date-input').datetimepicker({
    startDate: '+1971/05/01',
    format: 'd.m.Y',
    timepicker: false
  });
});
