import json
import logging
import os
import flask
import pymysql
from datetime import date
from flask import Flask, request, jsonify
from flask_httpauth import HTTPBasicAuth
from pymysql import IntegrityError

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False  # otherwise Flask would sort data alphabetically
port = 1080
auth = HTTPBasicAuth()
logging.basicConfig(level=logging.DEBUG)

rest_base_url = '/info/v1'

# Save env variables from run.sh
DB_HOST = os.environ['DB_HOST']
DB_PORT = int(os.environ['DB_PORT'])
DB_USER = os.environ['DB_USER']
DB_PASS = os.environ['DB_PASS']
DB_DBNAME = os.environ['DB_DBNAME']
HTTP_USER = os.environ['HTTP_USER']
HTTP_PASS = os.environ['HTTP_PASS']

USER_DATA = {
    HTTP_USER: HTTP_PASS
}

todays_date = date.today()

@auth.verify_password
def verify(username, password):
    if not (username and password):
        return False
    return USER_DATA.get(username) == password


def con_db():
    return pymysql.connect(host=DB_HOST, port=DB_PORT, db=DB_DBNAME, user=DB_USER, password=DB_PASS)


def make_error(status_code, description):
    response = jsonify({
        'description': description
    })
    response.status_code = status_code
    return response


def success():
    response = jsonify({
        'description': 'Successful operation'
    })
    response.status_code = 200
    return response


@app.route(rest_base_url + '/watch', methods=['POST'])
@auth.login_required
def add_watch():
    con = con_db()
    watch = json.loads(request.data)
    sql = 'INSERT INTO watches (sku, type, status, gender, year, dial_material, ' \
          'dial_color, case_material, case_form, bracelet_material, movement)' \
          'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'

    # init variables empty, and try to fill them with values received from json.
    sku = typ = status = gender = year = ''
    try:
        sku = str(watch['sku'])
        typ = str(watch['type'])
        status = str(watch['status'])
        gender = str(watch['gender'])
        year = int(watch['year'])
        assert typ == 'watch' or typ == 'chrono', 'Allowed values for type [watch|chrono].'
        assert status == 'old' or status == 'current' or status == 'outlet', 'Allowed values for gender [old|current|outlet].'
        assert gender == 'man' or gender == 'woman', 'Allowed values for gender [man|woman]'

        assert valid_year(year), 'Year is invalid. Allowed range [1900 - {0}]'.format(todays_date.year)
        assert sku != '' and typ != '' and status != '' and gender != '' and year != '', 'sku, type, status, gender and year are mandatory fields!'
    except KeyError:
        return make_error(400, 'Invalid input')
    except ValueError:
        return make_error(400, 'Invalid input: Field has wrong value.')
    except AssertionError as e:
        return make_error(400, 'Invalid input: %s' % e)

    d_mat = d_color = c_mat = c_form = b_mat = mov = ''
    try:
        d_mat = str(watch['dial_material'])
        d_color = str(watch['dial_color'])
        c_mat = str(watch['case_material'])
        c_form = str(watch['case_form'])
        b_mat = str(watch['bracelet_material'])
        mov = str(watch['movement'])
    except ValueError:
        pass
    except KeyError:
        # does not matter if optional parameter has value or not
        pass

    try:
        with con.cursor() as cur:
            cur.execute(sql, (sku, typ, status, gender, year, d_mat, d_color,
                              c_mat, c_form, b_mat, mov))
    except IntegrityError:
        return make_error(400, 'Invalid input: Watch already exists.')
    finally:
        con.commit()
        con.close()
    return success()


@app.route(rest_base_url + '/watch/<sku>', methods=['GET', 'PUT', 'DELETE'])
@auth.login_required
def query_watch(sku):
    con = con_db()
    select = 'SELECT * FROM watches WHERE sku LIKE %s'
    if request.method == 'GET':
        try:
            with con.cursor() as cur:
                cur.execute(select, sku)
                rows = cur.fetchall()
                if len(rows) != 1:
                    return make_error(404, 'Watch not found')
                else:
                    row_headers = [x[0] for x in cur.description]  # this will extract row headers
                    json_data = []
                    for result in rows:
                        json_data.append(dict(zip(row_headers, result)))
                    response = flask.make_response(jsonify(json_data[0]))
                    response.cache_control.max_age = 3600
                    return response
        finally:
            con.commit()
            con.close()

    if request.method == 'PUT':
        sql = 'UPDATE watches SET '
        # check if clock exists
        try:
            with con.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(select, sku)
                rows = cur.fetchall()
                if len(rows) != 1:
                    return make_error(404, 'Watch not found')
        except ConnectionError:
            con.close()

        watch = json.loads(request.data)
        params = {}
        try:
            for key in watch:
                # Validation
                if 'type' == key:
                    assert str(watch[key]) == 'watch' or str(watch[key]) == 'chrono', 'Allowed values for type [' \
                                                                                      'watch|chrono] '
                if 'status' == key:
                    assert str(watch[key]) == 'old' or str(watch[key]) == 'current' or str(watch[key]) == 'outlet' \
                        , 'Allowed values for gender [old|current|outlet]'
                if 'gender' == key:
                    assert str(watch[key]) == 'man' or str(watch[key]) == 'woman', 'Allowed values for gender [' \
                                                                                   'man|woman] '
                if 'year' == key:
                    assert valid_year(watch[key]), 'Year is invalid. Allowed range [1900 - {0}]'.format(todays_date.year)

                params[key] = str(watch[key])

        except KeyError:
            return make_error(400, 'Invalid input: Provide values for all mandatory parameters!')
        except AssertionError as e:
            return make_error(400, 'Invalid inputs: %s' % e)
        except ValueError:
            return make_error(400, 'Invalid input: ValueError')

        try:
            first_param = True
            with con.cursor() as cur:
                # building SQL query
                for key in params:
                    if first_param:
                        first_param = False
                        sql = sql + key + '=\'' + params[key] + '\''
                    else:
                        sql = sql + ' , ' + key + '=\'' + params[key] + '\''
                sql = sql + ' WHERE sku =\'' + sku + '\''

                cur.execute(sql)

        except IntegrityError:
            return make_error(400, 'Invalid input: Watch with this sku already exists')
        finally:
            con.commit()
            con.close()
        return success()

    if request.method == 'DELETE':
        sql = 'DELETE FROM watches WHERE sku LIKE %s'
        try:
            with con.cursor() as cur:
                cur.execute(select, sku)
                rows = cur.fetchall()
                if len(rows) != 1:
                    return make_error(404, 'Watch not found')
                else:
                    cur.execute(sql, sku)
        finally:
            con.commit()
            con.close()
        return success()


@app.route(rest_base_url + '/watch/complete-sku/<prefix>', methods=['GET'])
@auth.login_required
def get_list_by_prefix(prefix):
    con = con_db()
    sql = 'SELECT sku FROM watches WHERE sku LIKE %s'
    try:
        with con.cursor() as cur:
            cur.execute(sql, (prefix + '%',))
            rows = cur.fetchall()
            json_data = []
            for result in rows:
                json_data.append(result[0])
            response = flask.make_response(jsonify({'sku': json_data}))
            response.cache_control.max_age = 3600
            return response
    finally:
        con.commit()
        con.close()


@app.route(rest_base_url + '/watch/find', methods=['GET'])
@auth.login_required
def get_list_by_criteria():
    con = con_db()
    # building SQL query
    sql = 'SELECT * FROM watches WHERE '
    sql_and = ' AND '
    params = {'sku': request.args.get('sku'),
              'type': request.args.get('type'),
              'status': request.args.get('status'),
              'gender': request.args.get('gender'),
              'year': request.args.get('year')}

    first_param = True
    for key, value in params.items():
        if value is not None:
            if first_param:
                if key == 'sku':
                    sql = sql + key + ' LIKE \'' + value + '%\''
                else:
                    sql = sql + key + '=\'' + value + '\''
                first_param = False
            else:
                if key == 'sku':
                    sql = sql + sql_and + key + ' LIKE \'' + value + '%\''
                else:
                    sql = sql + sql_and + key + '=\'' + value + '\''

    logging.info(sql)  #see SQL query in console

    try:
        with con.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            if len(rows) == 0:
                return make_error(404, 'Watch not found')
            else:
                row_headers = [x[0] for x in cur.description]  # this will extract row headers
                json_data = []
                for result in rows:
                    json_data.append(dict(zip(row_headers, result)))
                response = flask.make_response(jsonify(json_data))
                response.cache_control.max_age = 3600
                return response
    finally:
        con.commit()
        con.close()


def valid_year(year):
    if year:
        return 1900 <= int(year) <= todays_date.year
    return False


if __name__ == '__main__':
    print('server listening on port: ' + str(port))
    app.run(port=port, debug=True, host='0.0.0.0')
