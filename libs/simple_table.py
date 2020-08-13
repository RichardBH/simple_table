from functools import reduce

from yatl.helpers import DIV, TABLE, TR, TD, TH, A, SPAN, I, THEAD, P, TAG

from py4web import request, URL, response
from .. import settings
from .. models import db
import uuid
import json

NAV = TAG.nav
HEADER = TAG.header


def get_signature():
    """
    if 'user_signature' specified in the query_parms, retrieve it and use that signature.  else,
    create a new one

    :return: user signature uuid
    """
    return request.query.get('user_signature', uuid.uuid4())


def get_storage_value(user_signature, filter_name, default_value=None):
    storage_value = default_value
    if user_signature and user_signature in request.cookies:
        cookie = json.loads(request.get_cookie(user_signature,
                                               default={},
                                               secret=settings.SESSION_SECRET_KEY))
        storage_value = cookie.get(filter_name, default_value)

    return storage_value


def set_storage_values(user_signature, values_dict):
    response.set_cookie(str(user_signature),
                        json.dumps(values_dict),
                        secret=settings.SESSION_SECRET_KEY,
                        max_age=settings.SIMPLE_TABLE_SIGNATURE_MAX_AGE)


class SimpleTable:
    def __init__(self,
                 endpoint,
                 queries,
                 search_form=None,
                 storage_values=None,
                 fields=None,
                 hidden_fields=None,
                 show_id=False,
                 orderby=None,
                 left=None,
                 headings=None,
                 per_page=settings.SIMPLE_TABLE_ROWS_PER_PAGE,
                 create_url='',
                 edit_url='',
                 delete_url='',
                 include_action_button_text=False,
                 user_signature=None):
        """
        SimpleTable is a searchable/sortable/pageable grid

        :param endpoint: the url of the page. used to build URLs for sorting/searching paging
        :param queries: list of queries used to filter the data
        :param search_form: py4web FORM to be included as the search form
        :param storage_values: values to save between requests
        :param fields: list of fields to display on the list page
        :param hidden_fields: fields included on the field list that should be hidden on the list page
        :param show_id: True/False - show the record id field on list page - default = False
        :param orderby: pydal orderby field or list of fields
        :param left: if joining other tables, specify the pydal left expression here
        :param headings: list of headings to be used for list page - if not provided use the field label
        :param per_page: # of rows to display per page - gets default from app settings
        :param create_url: URL to redirect to for creating records
        :param edit_url: URL to redirect to for editing records
        :param delete_url: URL to redirect to for deleting records
        :param include_action_button_text: include text on action buttons - default = False
        :param user_signature: id of the cookie containing saved values
        """
        self.query_parms = dict()
        if request.query_string and isinstance(request.query_string, str):
            #  split the key/value pairs
            kvp = request.query_string.split('&')
            for query_parm in kvp:
                #  split the parm into key and value
                key, value = query_parm.split('=')
                self.query_parms[key] = value

        #  get instance arguments
        self.endpoint = endpoint
        self.search_form = search_form

        self.query = reduce(lambda a, b: (a & b), queries)

        self.fields = []
        if fields:
            if isinstance(fields, list):
                self.fields = fields
            else:
                self.fields = [fields]

        self.hidden_fields = []
        if hidden_fields:
            if isinstance(hidden_fields, list):
                self.hidden_fields = hidden_fields
            else:
                self.hidden_fields = [hidden_fields]

        self.show_id = show_id
        self.orderby = orderby
        self.left = left

        self.headings = []
        if headings:
            if isinstance(headings, list):
                self.headings = headings
            else:
                self.headings = [headings]

        self.per_page = per_page
        sig_page_number = json.loads(request.query.get(user_signature, '{}')).get('page', 1)
        current_page_number = request.query.get('page', sig_page_number)
        self.current_page_number = current_page_number if isinstance(current_page_number, int) \
            else int(current_page_number)

        self.edit_url = edit_url
        self.delete_url = delete_url
        self.create_url = create_url

        parms = dict()
        #  try getting sort order from the request
        sort_order = request.query.get('sort')
        if not sort_order:
            #  see if there is a stored orderby
            sort_order = get_storage_value(user_signature, 'orderby')
            if not sort_order:
                #  use sort order passed in
                sort_order = self.orderby

        orderby = self.decode_orderby(sort_order)
        parms['orderby'] = orderby['orderby_expression']
        storage_values['orderby'] = orderby['orderby_string']
        if orderby['orderby_string'] != get_storage_value(user_signature, 'orderby'):
            #  user clicked on a header to change sort order - reset page to 1
            self.current_page_number = 1

        if self.left:
            parms['left'] = self.left

        if self.fields:
            self.total_number_of_rows = db(self.query).count()
        else:
            self.total_number_of_rows = db(self.query).count()

        #  if at a high page number and then filter causes less records to be displayed, reset to page 1
        if (self.current_page_number - 1) * per_page > self.total_number_of_rows:
            self.current_page_number = 1

        if self.total_number_of_rows > self.per_page:
            self.page_start = self.per_page * (self.current_page_number - 1)
            self.page_end = self.page_start + self.per_page
            parms['limitby'] = (self.page_start, self.page_end)
        else:
            self.page_start = 0
            if self.total_number_of_rows > 1:
                self.page_start = 1
            self.page_end = self.total_number_of_rows

        if self.fields:
            print('dal query parms', parms)
            self.rows = db(self.query).select(*fields, **parms)
        else:
            self.rows = db(self.query).select(**parms)

        self.number_of_pages = self.total_number_of_rows // self.per_page
        if self.total_number_of_rows % self.per_page > 0:
            self.number_of_pages += 1

        self.include_action_button_text = include_action_button_text
        self.user_signature = user_signature
        storage_values['page'] = self.current_page_number

        set_storage_values(user_signature, storage_values)
        self.storage_values = storage_values

    def decode_orderby(self, sort_order):
        """
        sort_order can be an int, string, list of strings, pydal fields or list of pydal fields

        need to determine which it is and then return a dict containing the string representation of the
        orderby and the pydal expression to be used in the query

        :param sort_order:
        :return: dict(orderby_string=<order by string>, orderby_expression=<pydal orderby expression>)
        """
        orderby_expression = None
        orderby_string = None
        if sort_order:
            #  can be an int or a PyDAL field
            try:
                index = int(sort_order)
                #  if we get here, this is a sort request from the table
                #  if it is in the saved order by then reverse the direction
                if (request.query.get('sort_dir') and request.query.get('sort_dir') == 'desc') or index < 0:
                    orderby_expression = [~self.fields[abs(index)]]
                else:
                    orderby_expression = [self.fields[index]]
            except:
                #  this could be:
                #  a string
                #  a list of strings
                #  a list of dal fields or a single pydal field, treat the same
                if isinstance(sort_order, str):
                    #  a string
                    tablename, fieldname = sort_order.split('.')
                    orderby_expression = [db[tablename][fieldname]]
                else:
                    sort_type = 'dal_field'
                    for x in sort_order:
                        if isinstance(x, str):
                            sort_type = 'str'

                    if sort_type == 'dal_field':
                        #  a list of dal fields
                        orderby_expression = sort_order
                    else:
                        #  a list of strings
                        orderby_expression = []
                        for x in sort_order:
                            tablename, fieldname = x.replace('~', '').split('.')
                            if '~' in x:
                                orderby_expression.append(~db[tablename][fieldname])
                            else:
                                orderby_expression.append(db[tablename][fieldname])
        else:
            for field in self.fields:
                if field not in self.hidden_fields and (field.name != 'id' or field.name == 'id' and self.show_id):
                    orderby_expression = field

        if orderby_expression:
            try:
                orderby_string = []
                for x in orderby_expression:
                    if ' DESC' in str(x):
                        orderby_string.append('~' + str(x).replace('"', '').replace(' DESC', ''))
                    else:
                        orderby_string.append('%s.%s' % (x.tablename, x.name))
            except:
                orderby_string = orderby_expression

        return dict(orderby_string=orderby_string, orderby_expression=orderby_expression)

    def iter_pages(self, left_edge=1, right_edge=1, left_current=1, right_current=2):
        """
        generator used to determine which page numbers should be shown on the SimpleTable pager

        :param left_edge: # of pages to show on the left
        :param right_edge: # of pages to show on the right
        :param left_current: # of pages to add to the left of current page
        :param right_current: # of fpages to add to the right of current page
        """
        current = 1
        last_blank = False
        while current <= self.number_of_pages:
            #  current page
            if current == self.current_page_number:
                last_blank = False
                yield current

            #  left edge
            elif current <= left_edge:
                last_blank = False
                yield current

            #  right edge
            elif current > self.number_of_pages - right_edge:
                last_blank = False
                yield current

            #  left of current
            elif self.current_page_number - left_current <= current < self.current_page_number:
                last_blank = False
                yield current

            #  right of current
            elif self.current_page_number < current <= self.current_page_number + right_current:
                last_blank = False
                yield current
            else:
                if not last_blank:
                    yield None
                    last_blank = True

            current += 1

    def __repr__(self):
        """
        build the query table

        :return: html representation of the table
        """
        _html = DIV(_class='field')
        _top_div = DIV(_style='padding-bottom: 1rem;')
        if self.create_url and self.create_url != '':
            _a = A('', _href=self.create_url,
                   _class='button')
            _span = SPAN(_class='icon is-small')
            _span.append(I(_class='fas fa-plus'))
            _a.append(_span)
            _a.append(SPAN('New'))
            _top_div.append(_a)

        #  build the search form if provided
        if self.search_form:
            _sf = DIV(_class='is-pulled-right')
            _sf.append(self.search_form.custom['begin'])
            _tr = TR()
            for field in self.search_form.table:
                _fs = SPAN(_style='padding-right: .5rem;')
                _td = TD(_style='padding-right: .5rem;')
                if field.type == 'boolean':
                    _fs.append(self.search_form.custom['widgets'][field.name])
                    _fs.append(field.label)
                    _td.append(self.search_form.custom['widgets'][field.name])
                    _td.append(field.label)
                else:
                    _fs.append(self.search_form.custom['widgets'][field.name])
                    _td.append(self.search_form.custom['widgets'][field.name])
                if field.name in self.search_form.custom['errors'] and self.search_form.custom['errors'][field.name]:
                    _fs.append(SPAN(self.search_form.custom['errors'][field.name], _style="color:#ff0000"))
                    _td.append(DIV(self.search_form.custom['errors'][field.name], _style="color:#ff0000"))
                _tr.append(_td)
            _tr.append(TD(self.search_form.custom['submit']))
            _sf.append(TABLE(_tr))
            for hidden_widget in self.search_form.custom['hidden_widgets'].keys():
                _sf.append(self.search_form.custom['hidden_widgets'][hidden_widget])

            _sf.append(self.search_form.custom['end'])
            _top_div.append(_sf)

        _html.append(_top_div)

        _table = TABLE(_class='table is-bordered is-striped is-hoverable is-fullwidth')

        # build the header
        _thead = THEAD()
        for index, field in enumerate(self.fields):
            if field not in self.hidden_fields and (field.name != 'id' or field.name == 'id' and self.show_id):
                try:
                    heading = self.headings[index]
                except:
                    heading = field.label
                #  add the sort order query parm
                sort_query_parms = dict(self.query_parms)
                sort_query_parms['sort'] = index
                current_sort_dir = 'asc'

                if '%s.%s' % (field.tablename, field.name) in self.storage_values['orderby']:
                    sort_query_parms['sort'] = -index
                    _h = A(heading.replace('_', ' ').upper(),
                           _href=URL(self.endpoint, vars=sort_query_parms))
                    _h.append(SPAN(I(_class='fas fa-sort-up'), _class='is-pulled-right'))
                elif '~%s.%s' % (field.tablename, field.name) in self.storage_values['orderby']:
                    _h = A(heading.replace('_', ' ').upper(),
                           _href=URL(self.endpoint, vars=sort_query_parms))
                    _h.append(SPAN(I(_class='fas fa-sort-down'), _class='is-pulled-right'))
                else:
                    _h = A(heading.replace('_', ' ').upper(),
                           _href=URL(self.endpoint, vars=sort_query_parms))


                if 'sort_dir' in sort_query_parms:
                    current_sort_dir = sort_query_parms['sort_dir']
                    del sort_query_parms['sort_dir']
                if index == int(request.query.get('sort', 0)) and current_sort_dir == 'asc':
                    sort_query_parms['sort_dir'] = 'desc'

                _th = TH()
                _th.append(_h)

                _thead.append(_th)

        if self.edit_url or self.delete_url:
            _thead.append(TH('ACTIONS', _style='text-align: center;'))

        _table.append(_thead)

        #  build the rows
        for row in self.rows:
            _tr = TR()
            for field in self.fields:
                if field not in self.hidden_fields and (field.name != 'id' or field.name == 'id' and self.show_id):
                    _tr.append(TD(row[field.name] if row and field and field.name in row and row[field.name] else ''))

            _td = None
            if (self.edit_url and self.edit_url != '') or (self.delete_url and self.delete_url != ''):
                _td = TD(_class='center', _style='text-align: center;')
                if self.edit_url and self.edit_url != '':
                    if self.include_action_button_text:
                        _a = A(_href=self.edit_url + '/%s?user_signature=%s&page=%s' % (row.id,
                                                                                        self.user_signature,
                                                                                        self.current_page_number),
                               _class='button is-small')
                        _span = SPAN(_class='icon is-small')
                        _span.append(I(_class='fas fa-edit'))
                        _a.append(_span)
                        _a.append(SPAN('Edit'))
                    else:
                        _a = A(I(_class='fas fa-edit'),
                               _href=self.edit_url + '/%s?user_signature=%s&page=%s' % (row.id,
                                                                                        self.user_signature,
                                                                                        self.current_page_number),
                               _class='button is-small')
                    _td.append(_a)
                if self.delete_url and self.delete_url != '':
                    if self.include_action_button_text:
                        _a = A(_href=self.delete_url + '/%s?user_signature=%s' % (row.id, self.user_signature),
                               _class='confirmation button is-small')
                        _span = SPAN(_class='icon is-small action-button-image')
                        _span.append(I(_class='fas fa-trash'))
                        _a.append(_span)
                        _a.append(SPAN('Delete'))
                    else:
                        _a = A(I(_class='fas fa-trash'),
                               _href=self.delete_url + '/%s?user_signature=%s' % (row.id, self.user_signature),
                               _class='confirmation button is-small', _message='Delete record ' +str(row.id) )
                    _td.append(_a)
                _tr.append(_td)
            _table.append(_tr)

        _html.append(_table)

        _row_count = DIV(_class='is-pulled-left')
        _row_count.append(
            P('Displaying rows %s thru %s of %s' % (self.page_start + 1 if self.number_of_pages > 1 else 1,
                                                    self.page_end if self.page_end < self.total_number_of_rows else
                                                    self.total_number_of_rows,
                                                    self.total_number_of_rows)))
        _html.append(_row_count)

        #  build the pager
        _pager = DIV(_class='is-pulled-right')
        for page_number in self.iter_pages():
            if page_number:
                pager_query_parms = dict(self.query_parms)
                pager_query_parms['page'] = page_number
                pager_query_parms['user_signature'] = self.user_signature
                if self.current_page_number == page_number:
                    _pager.append(A(page_number, _class='button is-primary is-small',
                                    _href=URL(self.endpoint, vars=pager_query_parms)))
                else:
                    _pager.append(A(page_number, _class='button is-small',
                                    _href=URL(self.endpoint, vars=pager_query_parms)))
            else:
                _pager.append('...')

        if self.number_of_pages > 1:
            _html.append(_pager)

        return str(_html)
