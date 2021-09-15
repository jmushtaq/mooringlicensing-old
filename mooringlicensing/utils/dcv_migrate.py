from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

import os
import subprocess
import json
import datetime
from decimal import Decimal

from oscar.apps.address.models import Country
from ledger.accounts.models import EmailUser, Address
from mooringlicensing.components.proposals.models import (
    Proposal,
    Vessel,
    Owner,
    VesselOwnership,
    VesselDetails,
    WaitingListApplication,
    ProposalUserAction,
    MooringBay,
)
from mooringlicensing.components.approvals.models import DcvOrganisation, DcvVessel, DcvPermit
from mooringlicensing.components.payments_ml.models import FeeSeason

class DcvMigration(object):
    '''
        from mooringlicensing.utils.waiting_list_migrate import DcvMigration, GrepSearch
        DcvMigration(test=False)
    '''

    def __init__(self, path='/var/www/mooringlicensing/mooringlicensing/utils/lotus_notes', test=False):
        self.path = path
        self.test = test

        self.company = self.read_dict('Charter_Operators___Company.json')
        self.surname = self.read_dict('Charter_Operators___Surname.json')

        self._company = [
              {
                "Company": "None",
                "PersNo": "208538",
                "LicenceType": "C",
                "NoVessel": "1",
                "EMail": "aussietigress@gmail.com",
                "_1": "P O Box 4287 Wellington Street, MOSMAN PARK, WA, 6012",
                "_3": "438999 - TIGRESS",
                "HIN1": "MH6632",
                "PhoneHome": "None",
                "PhoneMobile": "0409 680 200",
                "PhoneWork": "None",
                "EmailPromo": "Yes"
              },
              {
                "Company": "Boating West (Boat Hire)",
                "PersNo": "212521",
                "LicenceType": "C",
                "NoVessel": "3",
                "EMail": "info@boatingwest.com.au",
                "_1": "P O Box 8185, BROOME, WA, 6125",
                "_3": "438642 - TD1564",
                "HIN1": "None",
                "PhoneHome": "None",
                "PhoneMobile": "0429 887 798",
                "PhoneWork": "None",
                "EmailPromo": "Yes"
              },
        ]

        self._surname = [
              {
                '_2': 'Foster Alex',
                'PersNo': '212521',
                '_8': 'C',
                'NoVessel': '3',
                '_5': 'None',
                '_1': 'P O Box 8185, BROOME, WA, 6125',
                'DateCValid1': 'None',
                'StickerCNo1': 'None',
                'DateCSent1': 'None',
                '_3': '438642 - TD1564',
                'StickerCNo2': 'None',
                'DateCSent2': 'None',
                '_11': '439250 - TD1565',
                'StickerCNo3': 'None',
                'DateCSent3': 'None',
                '_12': '440866 - HD0705',
                'StickerCNo4': 'None',
                'DateCSent4': 'None',
                '_13': 'None',
                'StickerCNo5': 'None',
                'DateCSent5': 'None',
                '_14': 'None'
              }
        ]


        self.migrate()

    def read_dict(self, fname):
        filename = self.path + os.sep + fname if not self.path.endswith(os.sep) else self.path + fname
        with open(filename) as f:
            f_json = json.load(f)

            # make list unique
            _list = []
            for i in f_json:
                if i not in _list:
                    _list.append(i)

        return _list

    def search(self, key, value, records):
        for record in records:
            if value == record.get(key):
                return record
        return None

    def migrate(self):

        fee_season = FeeSeason.objects.get(name='2020-2021')
        start_date = datetime.date(2020, 9, 1)
        end_date = datetime.date(2021, 10, 7)

        address_list = []
        user_list = []
        dcv_vessel_list = []
        dcv_organisation_list = []
        dcv_permit_list = []

        added = []
        errors = []
        with transaction.atomic():
            #for idx, record in enumerate(self.waitlist[390:], 1):
            for idx, record in enumerate(self.company, 1):
                try: 
                    #import ipdb; ipdb.set_trace()
                    pers_no = record.get('PersNo')
                    email = record.get('EMail').split(';')[0].strip().lower()
                    org_name = record.get('Company') if record.get('Company') != 'None' else None
                    num_vessels = int(record.get('NoVessel'))
                    address = record.get('_1')
                    phone_no = record.get('PhoneHome')
                    mobile_no = record.get('PhoneMobile')
                    worke_no = record.get('PhoneWork')

                    surname_record = self.search('PersNo', pers_no, self.surname)

                    username = surname_record.get('_2')
                    firstname = username.split(' ')[-1]
                    lastname = ' '.join(username.split(' ')[:-1])

                    items = address.split(',')
                    line1 = items[0].strip()
                    line2 = items[1].strip() if len(items) > 3 else ''
                    line3 = items[2].strip() if len(items) > 4 else ''
                    state = items[-2].strip()
                    postcode = items[-1].strip()

                    #import ipdb; ipdb.set_trace()
                    print(f'{idx}, {pers_no}, {state}, {postcode}')
                    if self.test:
                        continue

                    try:
                        user = EmailUser.objects.get(email=email)
                    except:
                        user = EmailUser.objects.create(email=email, first_name=firstname, last_name=lastname, mobile_number=mobile_no, phone_number=phone_no)

                    country = Country.objects.get(printable_name='Australia')
                    address, address_created = Address.objects.get_or_create(line1=line1, line2=line2, line3=line3, postcode=postcode, state=state, country=country, user=user)
                    user.residential_address = address
                    user.postal_address = address
                    user.save()

                    dcv_organisation = None
                    if org_name:
                        try:
                            dcv_organisation = DcvOrganisation.objects.get(name=org_name)
                        except ObjectDoesNotExist: 
                            dcv_organisation = DcvOrganisation.objects.create(name=org_name)


                    for idx,i in enumerate(['_3', '_11', '_12', '_13', '_14'], 1):
                        items = surname_record[i].split('-')
                        rego_no = items[0].strip()
                        vessel_name = items[1].strip()
                        #print(surname[10][i])
                        print(f'\t{idx}, {rego_no}, {vessel_name}')


                        try:
                            dcv_vessel = DcvVessel.objects.get(rego_no=rego_no)
                        except ObjectDoesNotExist:
                            dcv_vessel = DcvVessel.objects.create(
                                rego_no = rego_no,
                                vessel_name = vessel_name,
                                dcv_organisation = dcv_organisation,
                            )

                        dcv_permit = DcvPermit.objects.create(
                            submitter = user,
                            lodgement_datetime = datetime.datetime.now(datetime.timezone.utc),
                            fee_season = fee_season,
                            start_date = start_date,
                            end_date = end_date,
                            dcv_vessel = dcv_vessel,
                            dcv_organisation =dcv_organisation,
                            migrated = True
                        )
                        dcv_permit.generate_dcv_permit_doc()

                        dcv_vessel_list.append(dcv_vessel.id)
                        dcv_permit_list.append(dcv_permit.id)

                        if idx == num_vessels:
                            break

                    address_list.append(address.id)
                    user_list.append(user.id)
                    if dcv_organisation:
                        dcv_organisation_list.append(dcv_organisation.id)

                    added.append(dcv_permit.id)

                except Exception as e:
                    #errors.append(str(e))
                    import ipdb; ipdb.set_trace()
                    raise Exception(str(e))

        print(f'Address.objects.get(id__in={address_list}).delete()')
        print(f'EmailUser.objects.get(id__in={user_list}).delete()')
        print(f'DcvVessel.objects.get(id__in={dcv_vessel_list}).delete()')
        print(f'DcvPermit.objects.get(id__in={dcv_permit_list}).delete()')
        print(f'DcvOrganisation.objects.get(id__in={dcv_organisation_list}).delete()')


def clear_migrated_dcv():
    pass

class GrepSearch(object):
    '''
    from mooringlicensing.utils.waiting_list_migrate import WaitingListMigration, GrepSearch

    GrepSearch('211305').search('PersNo', '_1')     --> Search for string PersNo='211305' in all files. The reult record/dict must also have key '_1' (i.e. the address)

    {'_3': 'AW670',
     'UserName': 'Mcintyre Michael',
     'PersNo': '211305',                            --> PersNo
     '_4': 'Au W',
     'RegLength1': '9.9',
     'NoVessel': '1',
     '_1': 'P O Box 4518, MYAREE BC, WA, 6960',     --> Address
     'PhoneHome': '9337 7228',                      --> PhoneHome
     'PhoneMobile': '0422 192 029',                 --> PhoneMobile
     'PhoneWork': 'None',                           --> PhoneWork
     'MooringNo': 'None',
     '_9': 'AU-TWA033401BQ5'}
    '''

    def __init__(self, search_str1, path='mooringlicensing/utils/lotus_notes'):
        self.path = path
        self.search_str1 = search_str1
        #self.search()

    def get_files(self, search_str):
        ''' Read all files in directory '''
        r=subprocess.check_output(['grep', '-rl', search_str, self.path])
        files = [i for i in r.decode('UTF-8').split('\n') if i.endswith(".json") ]
        return files

    def search(self, key1, key2):
        ''' Iteratively search for key:value pair in grep'd files '''

        def find(key, value, records):
            for record in records:
                if value == record.get(key):
                    return record
            return None

        #import ipdb; ipdb.set_trace()
        # Get all files that contains string 'self.search_str1'
        files = self.get_files(self.search_str1)

        for fname in files:
            with open(fname) as f:
                f_json = json.load(f)
                #import ipdb; ipdb.set_trace()
                # check the files (json) also has the key2
                if key2 in f_json[0]:
                    # find record in json that contains key1:search_str1
                    record = find(key1, self.search_str1, f_json)
                    if record:
                        #import ipdb; ipdb.set_trace()
                        if key2=='_1' and len(record['_1'].split(',')) <= 1:
                            continue
                        return record


