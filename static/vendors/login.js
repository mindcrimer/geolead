var system = require('system');
var args = system.args;

if (args.length < 3) {
  console.log('error: no_login_or_password');
  phantom.exit();
}

var page = require('webpage').create();

page.open('http://hosting.wialon.com/login.html', function() {
  page.onLoadFinished = function() {
    console.log(page.url);
    phantom.exit();
  };

  setTimeout(function() {
    page.evaluate(function(args) {
      console.log(args);
      document.forms[0].login.value = args[1];
      document.forms[0].passw.value = args[2];
      document.forms[0].submit();
    }, args);
  }, 1500);
});

