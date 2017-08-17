String.prototype.translit = (function(){
    var L = {
'А':'a','а':'a','Б':'b','б':'b','В':'v','в':'v','Г':'g','г':'g',
'Д':'d','д':'d','Е':'e','е':'e','Ё':'yo','ё':'yo','Ж':'zh','ж':'zh',
'З':'z','з':'z','И':'i','и':'i','Й':'y','й':'y','К':'k','к':'k',
'Л':'l','л':'l','М':'m','м':'m','Н':'n','н':'n','О':'o','о':'o',
'П':'p','п':'p','Р':'r','р':'r','С':'s','с':'s','Т':'t','т':'t',
'У':'u','у':'u','Ф':'f','ф':'f','Х':'kh','х':'kh','Ц':'ts','ц':'ts',
'Ч':'ch','ч':'ch','Ш':'sh','ш':'sh','Щ':'sch','щ':'sch','Ъ':'','ъ':'',
'Ы':'y','ы':'y','Ь':"",'ь':"",'Э':'e','э':'e','Ю':'yu','ю':'yu',
'Я':'ya','я':'ya',' ':'-', '.':'', ',':'', '&':'', '’':'', '»':'', '«':'',
'!':'', '–':'-','%':''
        },
        r = '',
        k;
    for (k in L) r += k;
    r = new RegExp('[' + r + ']', 'g');
    k = function(a){
        return a in L ? L[a] : '';
    };
    return function(){
        return this.replace(r, k).toLowerCase();
    };
})();

$(document).ready(function(e){
	$('#id_title,#id_title_en,#id_title_ru').blur(function() {
		var slugField = $('#id_slug');
		var slugVal = $.trim(slugField.val());
		var maxLength = slugField.attr('maxlength') || 100;
		if(!slugVal) {
			slugField.val($.trim($(this).val()).translit().substr(0, maxLength));
		}
	});
});
