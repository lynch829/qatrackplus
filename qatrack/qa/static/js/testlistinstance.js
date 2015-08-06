/**************************************************************************/
//Initialize sortable/filterable test list table data types
function init_test_list_instance_tables(units, frequencies){

    var unit_names = _.pluck(units[0].objects,"name");
    var freq_names = _.map(frequencies[0].objects,function(e){return {value:e.id,label:e.name};});
    freq_names.push({value:null,label:"Ad hoc"});

    var pagination = [$("#filtered_records").val(),$("#total_records").val()];

    var cols = [
        {bSortable:false},
        null,
        null,
        null,
        null,
        null,
        {bSortable:false},
        {bSortable:false}
    ];

    var filter_cols = [
        null, //action
        {type: "select",values:unit_names }, // unit
        {type: "select",values:freq_names }, //Freq
        {type: "text"}, //Test List
        null, //work completed
        {type: "text"},//user
        null,
        null //pass/fail status
    ];

    $("#testlistinstance-table").dataTable({
        bProcessing:true,
        bServerSide:true,
        sAjaxSource:"./",
        sAjaxDataProp:"data",
        bAutoWidth:false,
        fnAdjustColumnSizing:false,
        fnPreDrawCallback:function(){$("#pagination-placeholder").remove()},
        bFilter:true,
        bPaginate:true,
        bStateSave:true, /*remember filter/sort state on page load*/
        iDisplayLength:50,
        iDeferLoading:pagination,
        aaSorting:[[1,"asc"],[4,"desc"]],
        aoColumns:cols,
        sDom: '<"row-fluid"<"span6"ir><"span6"p>>t<"row-fluid"<"span12"lp>>',
        sPaginationType: "bootstrap"

    }).columnFilter({
        sPlaceHolder: "head:after",
        aoColumns: filter_cols,
        iFilteringDelay:250
    });

    $("#testlistinstance-table").find("select, input").addClass("input-small");
}

/**************************************************************************/
$(document).ready(function(){

    $.when(
        $.getJSON(QAURLs.API_URL+"unit/?format=json&limit=0"),
        $.getJSON(QAURLs.API_URL+"frequency/?format=json&limit=0")
    ).then(init_test_list_instance_tables);

});

