# py4web simple table

A collection of different ways to display a grid in py4web.

* Simple Table - My shot at a reusable table
* HTML Grid - the HTML grid from py4web
* Datatables.net - sample implementation of a reusable datatables.net table

All three examples are working over the same sqlite database of zip code I downloaded freely from the web which contains just over 42,000 records.

##### This is a work in progress

Random thoughts on each

#### Simple Table

* Delete not coded
* user_signature is a variable I pass through url arguments which gives me the cookie containing the parameters.  Trying to get this work work but having issues on returning from editing a record.
* currently the id field must be included in fields passed to SimpleTable - will be adding a show or hide id parm

The concept for filtering is that you define and manage your own filter form and the querying done with the results.

#### HTML Grid
* I like my edit buttons the right side of each row - I need to work on adding that
* Paging seems to be off a little bit - I will submit a PR
* filtering - if you return no rows, you lose all your column header except for the ones where there is a filter
* the paging buttons move around too much - I like to be able to page without moving my mouse.  The next button moves around based on the text before it (obviously).  Would like a different paging control.
* formatting - I seem to recall Massimo saying we needed to add some standardized css classes so people can modify the look and feel.

#### datatables.net
* biggest concern here is formatting/presentation.  I'm using bulma in py4web but there is no official bulma skin for datatables.net.  Need to look into formatting options.  UPDATE 8/11/2020 - I've made lots of formatting changes.  More to come but got a good start tonight.
* edit controls - I have the edit controls placed where I want them - just need to insert the urls for the edit pages - Coming soon
* my implementation uses a specific view page.  I need to make it more granular so you can include the javascript in one spot and specify the element id for where the table lives
 
