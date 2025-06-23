$(document).ready(function(){
	$('.hidden').hide();

	/**
	 * For tables with select all option check if all checkboxes are selected.
	 * If one of them is unchecked then uncheck the main select all checkbox.
	*/
	$('.account-datatable tbody tr td.checkbox-td input[type="checkbox"]').click(function(){
		name = $(this).attr('name').split(":list")[0];
		if($(this).attr('class') != 'selectall'){
			if($(this).attr('checked') == false){
				$('.selectall').attr('checked', false);
				$(this).attr('checked', false);
			}else {
				var not_all = false;
				$.each($('.account-datatable tbody tr td.checkbox-td input[@name="' + name + '"][type="checkbox"]'), function(i, e){
					if($(this).attr('checked') == false){
						not_all = true;
					}
				});
				if(not_all == false){
					$('.selectall').attr('checked', true);
				}
			}
		}
	});
});

function toggleView(selector){
	$(selector).toggle();
	return false;
}

function selectAll(name, additional_class){
    var table_class = '.account-datatable';
    if ( additional_class ){
        table_class += '.' + additional_class;
    }

    $('' + table_class + ' tbody tr td.checkbox-td input[@name="' + name + '"][type="checkbox"]').each(function(){
        $this = $(this);
        if ( $this.attr('checked') == true ) {
            $this.attr('checked', false);
        }else {
            $this.attr('checked', true);
        }
    });
    return false;
}

(function(){
	jQuery(document).ready(function(){
		/** User admin **/
		jQuery("input[name=send_confirmation]").click(function(ev){
			if(this.checked){
				jQuery("#confirmation_email").show('blind', {}, 800);
				jQuery.post(
					'confirmation_email',
					{'first_name:utf8:ustring': jQuery("#edit-first_name").val(),
					 user_id: jQuery("#edit-id").val()},
					 function(data){
						jQuery("#confirmation_email pre").text(data);
					 }
				);
			}
			else{
				jQuery("#confirmation_email").hide('blind', {}, 600);
			}
		});
	});
})();

// edit role name
(function($){

	var set_role_name = function (ev){
		var fieldsContainer = $("#role-name-edit");
		var role_name = $("input[name=role_name]", fieldsContainer).val();
		var role_description = $("textarea[name=role_description]", fieldsContainer).val();
		var role_status = $("select[name=role_status]", fieldsContainer).val();
		var role_id = $("input[name=role_id]", fieldsContainer).val();
		if(!role_name){
			alert("You must provide a name for the role");
		}
		else
			$.post('edit_role_name',
				{
					role_id: role_id,
					'role_name:utf8:ustring': role_name,
					'role_description:utf8:ustring': role_description,
					'role_status:utf8:ustring': role_status,
				},
				function(data){
					console.log(data);
					if(data.error)
						alert(data.error);
					else{
						$('div#role-name h1').text(role_name);
						$('#role-description').text(role_description);
						$('div#role-name-edit').hide(200, function(){
							$('div#role-name').show();
						});
					}
				},
				'json');
	};

	$(document).ready(function(){
		$("#edit-role-description-arrow").click(function(ev){
			$('div#role-name').hide(200, function(){
				$('div#role-name-edit').show();
			});
		});
		$("#role-name-edit input[name=role_name]").keypress(function(ev){
			if (ev.keyCode == 13)
				set_role_name(ev);
		});
		$("#role-name-edit input[type=submit]").click(set_role_name);
		$("#role-name-edit-cancel").click(function() {
			$('div#role-name-edit').hide(200, function(){
				$('div#role-name').show();
			});
		});
	});
})(jQuery);
