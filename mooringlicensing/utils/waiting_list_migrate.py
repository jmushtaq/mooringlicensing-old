import os
import subprocess
import json
import datetime
from decimal import Decimal
from django.db import transaction
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
from mooringlicensing.components.approvals.models import Approval, ApprovalHistory, WaitingListAllocation

class WaitingListMigration(object):

    #def __init__(self, path='/var/www/mooringlicensing/mooringlicensing/utils/wait_list/unique', test=False):
    def __init__(self, path='/var/www/mooringlicensing/mooringlicensing/utils/lotus_notes', test=False):
        self.path = path
        self.test = test

        self.waitlist = self.read_dict('Waitlist___Bay.json')

        self._waitlist = [
#             {
#              '_5': 'Catherine Bay',
#              '_3': '1',
#              'DateApplied': '2016-01-20 00:00:00',
#              'BayPosNo': '10',
#              '_6': 'None',
#              'UserName': 'Mcintyre Michael',
#              'PersNo': '211305',
#              'VesName': 'TOI',
#              'VesRego': 'AW670',
#              'RegLength': '9.9',
#              'Draft': '1.4',
#              'TrimNo': '16/00619'
#             },
#             {'_5': 'Catherine Bay',
#              '_3': '1',
#              'DateApplied': '2016-03-18 00:00:00',
#              'BayPosNo': '2',
#              '_6': 'None',
#              'UserName': 'Moffat Adam',
#              'PersNo': '211389',
#              'VesName': 'GOODWIN LONGBOAT',
#              'VesRego': 'BY341',
#              'RegLength': '6.7',
#              'Draft': '0.5',
#              'TrimNo': '16/00645'i
#             },
              {'_5': 'Thomson Bay', '_3': '1', 'DateApplied': '2017-07-21', 'BayPosNo': '79', '_6': 'None', 'UserName': 'Zanetti Paul', 'PersNo': '209448', 'VesName': 'MAXIMUS', 'VesRego': 'ER661', 'RegLength': '14', 'Draft': '1.4', 'TrimNo': '19/01107'},
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

        #import ipdb; ipdb.set_trace()
        return _list

    def search(self, key, value, records):
        for record in records:
            if value == record.get(key):
                return record
        return None

    def migrate(self):

        submitter = EmailUser.objects.get(email='jawaid.mushtaq@dbca.wa.gov.au')
        expiry_date = datetime.date(2021,11,30)

        address_list = []
        user_list = []
        vessel_list = []
        owner_list = []
        ownership_list = []
        details_list = []
        proposal_list = []
        wl_list = []
        user_action_list = []
        approval_list = []
        approval_history_list = []
        wla_list = []

        added = []
        errors = []
        with transaction.atomic():
            for idx, record in enumerate(self.waitlist[390:], 1):
            #for idx, record in enumerate(self.waitlist, 1):
                try: 
                    #import ipdb; ipdb.set_trace()
                    pers_no = record.get('PersNo')
                    email_record = GrepSearch(pers_no).search('PersNo', 'EMail')
                    address_record = GrepSearch(pers_no).search('PersNo', '_1')

                    phonemobile_record = {}
                    if 'PhoneMobile' not in address_record:
                        phonemobile_record = GrepSearch(pers_no).search('PersNo', 'PhoneMobile')
                    else:
                        phonemobile_record = address_record
                        
                    phonehome_record = {}
                    if 'PhoneHome' not in address_record:
                        phonehome_record = GrepSearch(pers_no).search('PersNo', 'PhoneHome')
                    else:
                        phonehome_record = address_record
                        
                    email = email_record.get('EMail')
                    mobile_no = phonemobile_record.get('PhoneMobile')
                    username = record.get('UserName')
                    firstname = username.split(' ')[-1]
                    lastname = ' '.join(username.split(' ')[:-1])

                    try:
                        phone_no = phonehome_record.get('PhoneHome') if phonehome_record else ''
                        address = address_record.get('_1') 
                    except:
                        import ipdb; ipdb.set_trace()

                    rego_no = record.get('VesRego')
                    vessel_type = 'other'
                    vessel_name = record.get('VesName')
                    vessel_overall_length = Decimal( record.get('RegLength') )
                    vessel_draft = Decimal( record.get('Draft') )
                    vessel_weight = Decimal( 0.0 )
                    berth_mooring = record.get('_5')
                     
                    if MooringBay.objects.filter(name=berth_mooring).count()>0:
                        mooring_bay = MooringBay.objects.filter(name=berth_mooring)[0]
                    else:
                        mooring_bay = MooringBay.objects.get(name='Rottnest Island')
                        #mooring_bay = MooringBay.objects.get(name='Thomson Bay')

#                    In [43]: for i in l:
#                        ...:     if MooringBay.objects.filter(name=i).count()>0:
#                        ...:         print(MooringBay.objects.filter(name=i))
#                        ...: 
#                    <QuerySet [<MooringBay: Geordie Bay>]>
#                    <QuerySet [<MooringBay: Longreach Bay>]>
#                    <QuerySet [<MooringBay: Thomson Bay>]>
#
#                    In [44]: l --> mooring names in Waitlist___Bay.json
#                    Out[44]: 
#                    ['Catherine Bay',
#                     'Geordie Bay',
#                     'Longreach Bay',
#                     'Marjorie Bay',
#                     'Narrow Neck',
#                     'Porpoise Bay',
#                     'Stark Bay',
#                     'Thomson Bay']

                    # needed ??
                    date_applied = record.get('DateApplied')
                    position_no = int(record.get('BayPosNo'))
                    trim_no = record.get('TrimNo')
                    percentage = 100

                 
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

                    vessel, rego_created = Vessel.objects.update_or_create(rego_no=rego_no)
                    owner, owner_created = Owner.objects.update_or_create(emailuser=user)
                    vessel_ownership, ownership_created = VesselOwnership.objects.update_or_create(
                        owner=owner,
                        vessel=vessel,
                        percentage=percentage
                    )
         
                    vessel_details, details_created = VesselDetails.objects.update_or_create(
                        vessel_type=vessel_type,
                        vessel=vessel,
                        vessel_name=vessel_name,
                        vessel_overall_length=vessel_overall_length,
                        vessel_length=vessel_overall_length,
                        vessel_draft=vessel_draft,
                        vessel_weight= vessel_weight,
                        berth_mooring=berth_mooring
                    )
                    
                    proposal=WaitingListApplication.objects.create(
                        proposal_type_id=1, 
                        submitter=user, 
                        migrated=True, 
                        vessel_details=vessel_details, 
                        vessel_ownership=vessel_ownership, 
                        rego_no=rego_no,
                        vessel_type=vessel_type,
                        vessel_name=vessel_name,
                        vessel_overall_length=vessel_overall_length,
                        vessel_length=vessel_overall_length,
                        vessel_draft=vessel_draft,
                        #vessel_beam='',
                        vessel_weight=vessel_weight,
                        berth_mooring=berth_mooring,
                        preferred_bay=mooring_bay,
                        percentage=percentage,
                        individual_owner=True,
                        proposed_issuance_approval={},
                        processing_status='approved',
                        customer_status='approved',
                    )

                    ua=ProposalUserAction.objects.create(
                        proposal=proposal,
                        who=user,
                        what='Waiting List - Migrated Application',
                    )

                    try:
                        start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').date()
                    except:
                        start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d').date()

                    approval = WaitingListAllocation.objects.create(
                        status='current',
                        internal_status='waiting',
                        current_proposal=proposal,
                        issue_date = datetime.datetime.now(datetime.timezone.utc),
                        #start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').date(),
                        start_date = start_date,
                        expiry_date = expiry_date,
                        submitter=submitter,
                        migrated=True,
                        wla_order=position_no,
                    )
                    #print(f'wla_order: {position_no}')

                    proposal.approval = approval
                    proposal.save()

                    try:
                        start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').astimezone(datetime.timezone.utc)
                    except:
                        start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d').astimezone(datetime.timezone.utc)

                    approval_history = ApprovalHistory.objects.create(
                        reason='new',
                        approval=approval,
                        vessel_ownership = vessel_ownership,
                        proposal = proposal,
                        #start_date = datetime.datetime.strptime(date_applied, '%Y-%m-%d %H:%M:%S').astimezone(datetime.timezone.utc)
                        start_date = start_date,
                    )

                    added.append(proposal.id)

                    address_list.append(address.id)
                    user_list.append(user.id)
                    vessel_list.append(vessel.id)
                    owner_list.append(owner.id)
                    ownership_list.append(vessel_ownership.id)
                    details_list.append(vessel_details.id)
                    proposal_list.append(proposal.proposal.id)
                    wl_list.append(proposal.id)
                    user_action_list.append(ua.id)
                    approval_list.append(approval.id)
                    approval_history_list.append(approval_history.id)

                except Exception as e:
                    #errors.append(str(e))
                    import ipdb; ipdb.set_trace()
                    raise Exception(str(e))

        print(f'Address.objects.get(id__in={address_list}).delete()')
        print(f'EmailUser.objects.get(id__in={user_list}).delete()')
        print(f'Vessel.objects.get(id__in={vessel_list}).delete()')
        print(f'Owner.objects.get(id__in={owner_list}).delete()')
        print(f'VesselOwnership.objects.get(id__in={ownership_list}).delete()')
        print(f'VesselDetails.objects.get(id__in={details_list}).delete()')
        print(f'WaitingListApplication.objects.get(id__in={wl_list}).delete()')
        print(f'ProposalUserAction.objects.get(id__in={user_action_list}).delete()')
        print(f'WaitingListAllocation.objects.get(id__in={approval_list}).delete()')
        print(f'ApprovalHistory.objects.get(id__in={approval_history_list}).delete()')

#        print(f'Vessels:   {vessel_list}')
#        print(f'Owners:    {owner_list}')
#        print(f'Ownership: {ownership_list}')
#        print(f'Details:   {ownership_list}')
#        print(f'Proposals: {ownership_list}')
#        print(f'Actions:   {user_action_list}')
#        print(f'Approvals: {approval_list}')
#        print(f'Approval_History: {approval_history_list}')
#        print(f'Added:     {len(added)}\n{added}')
#        print(f'Errors:    {len(errors)}\n{errors}')
#
#
#                    Address.object.get(id=address.id)
#                    EmailUser.object.get(id=user.id)
#                    Vessel.object.get(id=vessel.id)
#                    Owner.object.get(id=owner.id)
#                    VesselOwnership.object.get(id=vessel_ownership.id)
#                    VesselDetails.object.get(id=vessel_details.id)
#                    WaitingListApplication.object.get(id=proposal.id)
#                    ProposalUserAction.object.get(id=ua.id)
#                    WaitingListAllocation.object.get(id=approval.id)
#                    ApprovalHistory.object.get(id=approval_history.id)

def clear_record():
    Address.objects.last().delete()
    EmailUser.objects.last().delete()
    Vessel.objects.last().delete()
    Owner.objects.last().delete()
    VesselOwnership.objects.last().delete()
    VesselDetails.objects.last().delete()
    WaitingListApplication.objects.last().delete()
    ProposalUserAction.objects.last().delete()
    WaitingListAllocation.objects.last().delete()
    ApprovalHistory.objects.last().delete()

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

class GrepSearch2(object):

    #def __init__(self, path='/var/www/mooringlicensing/mooringlicensing/utils/lotus_notes'):
    def __init__(self, search_str1, search_str2, path='mooringlicensing/utils/lotus_notes'):
        self.path = path
        self.search_str1 = search_str1
        self.search_str2 = search_str2
        #self.search()

    def get_files(self, search_str):
        ''' Read all files in directory '''
        r=subprocess.check_output(['grep', '-rl', search_str, self.path])
        files = [i for i in r.decode('UTF-8').split('\n') if i.endswith(".json") ]
        return files

    def search(self, key):
        ''' Iteratively search for key:value pair in grep'd files '''

        def find(key, value, records):
            for record in records:
                if value == record.get(key):
                    return record
            return None

        import ipdb; ipdb.set_trace()
        file_list1 = self.get_files(self.search_str1)
        file_list2 = self.get_files(self.search_str2)
        files = list(set(file_list1).intersection(file_list2))

        for fname in files:
            with open(fname) as f:
                f_json = json.load(f)
                import ipdb; ipdb.set_trace()
                if self.search_str2 in f_json[0]:
                    record = find(key, self.search_str1, f_json)
                    if record:
                        return record

