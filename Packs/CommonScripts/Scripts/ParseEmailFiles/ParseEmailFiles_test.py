# coding=utf-8
from __future__ import print_function

import pytest

import demistomock as demisto
from CommonServerPython import entryTypes
from ParseEmailFiles import MsOxMessage, main, convert_to_unicode, unfold, handle_msg, get_msg_mail_format, \
    data_to_md, create_headers_map, DataModel, handle_eml, parse_nesting_level


def exec_command_for_file(
        file_path,
        info="RFC 822 mail text, with CRLF line terminators",
        file_name=None,
        file_type="",
):
    """
    Return a executeCommand function which will return the passed path as an entry to the call 'getFilePath'

    Arguments:
        file_path {string} -- file name of file residing in test_data dir

    Raises:
        ValueError: if call with differed name from getFilePath or getEntry

    Returns:
        [function] -- function to be used for mocking
    """
    if not file_name:
        file_name = file_path
    path = 'test_data/' + file_path

    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': path,
                        'name': file_name
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': info,
                        'type': file_type
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    return executeCommand


def test_msg_html_with_attachments():
    msg = MsOxMessage('test_data/html_attachment.msg')
    assert msg is not None
    msg_dict = msg.as_dict(max_depth=2)
    assert 'This is an html email' in msg_dict['Text']
    attachments_list = msg.get_all_attachments()
    assert len(attachments_list) == 1
    attach = attachments_list[0]
    assert attach.AttachFilename == 'dummy-attachment.txt'
    assert attach.AttachMimeTag == 'text/plain'
    assert attach.data == 'This is a text attachment'


def test_msg_utf_encoded_subject():
    msg = MsOxMessage('test_data/utf_subject.msg')
    assert msg is not None
    msg_dict = msg.as_dict(max_depth=2)
    # we test that subject which has utf-8 encoding (in the middle) is actually decoded
    assert '?utf-8' in msg_dict['HeadersMap']['Subject']
    subj = msg_dict['Subject']
    assert 'TESTING' in subj and '?utf-8' not in subj


def test_eml_smtp_type(mocker):
    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/smtp_email_type.eml',
                        'name': 'smtp_email_type.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'SMTP mail, UTF-8 Unicode text, with CRLF terminators'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    # assert demisto.executeCommand('getFilePath', {})[0]['Type'] == entryTypes['note']
    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Test Smtp Email'


# this is a test for another version of a multipart signed eml file
def test_smime2(mocker):
    multipart_sigened = 'multipart/signed; protocol="application/pkcs7-signature";, ASCII text, with CRLF line terminators'

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('smime2.p7m', info=multipart_sigened))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    # assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    # assert results[0]['EntryContext']['Email']['Subject'] == 'Testing signed multipart email'
    assert results[0]['EntryContext']['Email']['Subject'] == 'Testing signed multipart email'


def test_handle_eml_parses_correct_message_id():
    """
    Given:
     - eml file

    When:
     - parsing eml file into email data.

    Then:
     - Validate that correct 'Message-ID' case sensitive is in 'HeadersMap' dict.
       Must be 'Message-ID' case sensitive.

    """
    email_data, _ = handle_eml(file_path='test_data/invalid_message_id.eml')
    assert 'Message-ID' in email_data['HeadersMap']


def test_eml_contains_eml(mocker):
    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/Fwd_test-inner_attachment_eml.eml',
                        'name': 'Fwd_test-inner_attachment_eml.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'news or mail text, ASCII text'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 5
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email'][0]['Subject'] == 'Fwd: test - inner attachment eml'
    assert 'ArcSight_ESM_fixes.yml' in results[0]['EntryContext']['Email'][0]['Attachments']
    assert 'ArcSight_ESM_fixes.yml' in results[0]['EntryContext']['Email'][0]['AttachmentsData'][0]['Name']
    assert 'test - inner attachment eml.eml' in results[0]['EntryContext']['Email'][0]['Attachments']
    assert 'test - inner attachment eml.eml' in results[0]['EntryContext']['Email'][0]['AttachmentsData'][1]['Name']
    assert results[0]['EntryContext']['Email'][0]['Depth'] == 0
    assert results[0]['EntryContext']['Email'][1]["Subject"] == 'test - inner attachment eml'
    assert 'CS Training 2019 - EWS.pptx' in results[0]['EntryContext']['Email'][1]["Attachments"]
    assert 'CS Training 2019 - EWS.pptx' in results[0]['EntryContext']['Email'][1]["AttachmentsData"][0]['Name']
    assert results[0]['EntryContext']['Email'][1]['Depth'] == 1


def test_eml_contains_msg(mocker):
    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/DONT_OPEN-MALICIOUS.eml',
                        'name': 'DONT_OPEN-MALICIOUS.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'news or mail text, ASCII text'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 3
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email'][0]['Subject'] == 'DONT OPEN - MALICIOS'
    assert results[0]['EntryContext']['Email'][0]['Depth'] == 0

    assert 'Attacker+email+.msg' in results[0]['EntryContext']['Email'][0]['Attachments']
    assert 'Attacker+email+.msg' in results[0]['EntryContext']['Email'][0]['AttachmentsData'][0]['Name']
    assert results[0]['EntryContext']['Email'][1]["Subject"] == 'Attacker email'
    assert results[0]['EntryContext']['Email'][1]['Depth'] == 1


def test_eml_contains_eml_depth(mocker):
    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/Fwd_test-inner_attachment_eml.eml',
                        'name': 'Fwd_test-inner_attachment_eml.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'news or mail text, ASCII text'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '1'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 3
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Fwd: test - inner attachment eml'
    assert 'ArcSight_ESM_fixes.yml' in results[0]['EntryContext']['Email']['Attachments']
    assert 'ArcSight_ESM_fixes.yml' in results[0]['EntryContext']['Email']['AttachmentsData'][0]['Name']
    assert 'test - inner attachment eml.eml' in results[0]['EntryContext']['Email']['Attachments']
    assert 'test - inner attachment eml.eml' in results[0]['EntryContext']['Email']['AttachmentsData'][1]['Name']
    assert isinstance(results[0]['EntryContext']['Email'], dict)
    assert results[0]['EntryContext']['Email']['Depth'] == 0


def test_eml_utf_text(mocker):
    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/utf_8_email.eml',
                        'name': 'utf_8_email.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'UTF-8 Unicode text, with very long lines, with CRLF line terminators'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Test UTF Email'


def test_eml_utf_text_with_bom(mocker):
    '''Scenario: Parse an eml file that is UTF-8 Unicode (with BOM) text

    Given
    - A UTF-8 encoded eml file with BOM

    When
    - Executing ParseEmailFiles automation on the uploaded eml file

    Then
    - Ensure eml email file is properly parsed
    '''

    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/utf_8_with_bom.eml',
                        'name': 'utf_8_with_bom.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'RFC 822 mail text, UTF-8 Unicode (with BOM) text, '
                                'with very long lines, with CRLF line terminators'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Test UTF Email'


def test_email_with_special_character(mocker):
    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/email_with_special_char_bytes.eml',
                        'name': 'email_with_special_char_bytes.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'RFC 822 mail text, ISO-8859 text, with very long lines, with CRLF line terminators'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '1'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Hello dear friend'


@pytest.mark.parametrize('encoded_subject, decoded_subject', [
    (
        '[TESTING] =?utf-8?q?=F0=9F=94=92_=E2=9C=94_Votre_colis_est_disponible_chez_votre_co?= '
        '=?utf-8?q?mmer=C3=A7ant_Pickup_!?=',
        # noqa E501
        '[TESTING]\xf0\x9f\x94\x92 \xe2\x9c\x94 Votre colis est disponible chez votre commer\xc3\xa7ant Pickup !'
    ),
    (
        'This =?UTF-8?B?VGVzdMKu?= passes',
        'This Test® passes'
    ),
    (
        '=?utf-8?B?44CQ?= =?utf-8?B?4pGg?=',  # test case: double utf-8 byte encoded
        '\xe3\x80\x90\xe2\x91\xa0'  # 【①
    ),
    (
        '=?iso-2022-jp?B?GyRCJWEhPCVrLSEkSHxxGyhC?= '
        '=?iso-2022-jp?B?GyRCRnxLXDhsSjg7eiQsST08KCQ1JGwkSiQkSjg7eiROJUYlOSVIGyhC?=',
        'メール�と�日本語文字が表示されない文字のテスト'
    ),
    (
        '=?UTF-8?Q?TEST_UNDERSCORE?=',
        'TEST UNDERSCORE'
    ),
    # (
    #   'This is test =?iso-2022-jp?B?GyRCJWEhPCVrLSEkSHxxGyhC?= '
    #   '=?iso-2022-jp?B?GyRCRnxLXDhsSjg7eiQsST08KCQ1JGwkSiQkSjg7eiROJUYlOSVIGyhC?=',
    #   'This is test メール�と�日本語文字が表示されない文字のテスト'
    # )
    # ( 'Test =?UTF-8?Q?Seguran=C3=A7a=20?=da =?UTF-8?Q?Informa=C3=A7=C3=A3o?=',
    #   'Test Segurança da Informação'
    #  )
    # This test should pass, it extend the case of This example "=?UTF-8?B?VGVzdMKu?= passes" and include multiple
    # encoding parts.
    # **please DO NOT delete the commented tests**.
    # they have been disabled in attempt to fix issue no. 40877, and they may be needed for a better solution in the future.
])
def test_utf_subject_convert(encoded_subject, decoded_subject):
    decoded = convert_to_unicode(encoded_subject)
    assert decoded == decoded_subject
    assert 'utf-8' not in decoded


def test_unfold():
    assert unfold('test\n\tthis') == 'test this'
    assert unfold('test\r\n\tthis') == 'test this'
    assert unfold('test   \r\n this') == 'test this'


def test_email_raw_headers(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '1'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('multiple_to_cc.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['From'] == 'test@test.com'
    assert results[0]['EntryContext']['Email']['To'] == 'test@test.com, example1@example.com'
    assert results[0]['EntryContext']['Email']['CC'] == 'test@test.com, example1@example.com'
    assert results[0]['EntryContext']['Email']['HeadersMap']['From'] == 'Guy Test <test@test.com>'
    assert results[0]['EntryContext']['Email']['HeadersMap']['To'] == 'Guy Test <test@test.com>' \
                                                                      ', Guy Test1 <example1@example.com>'
    assert results[0]['EntryContext']['Email']['HeadersMap']['CC'] == 'Guy Test <test@test.com>, ' \
                                                                      'Guy Test1 <example1@example.com>'


def test_email_raw_headers_from_is_cyrillic_characters(mocker):
    """
    Given:
     - The email message the should pe parsed.
     - Checking an email file that contains '\r\n' in it's 'From' header.

    When:
     - After parsed email file into Email object

    Then:
     - Validate that all raw headers are valid.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '1'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('multiple_to_cc_from_Cyrillic'
                                                                                     '_characters.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['From'] == 'no-reply@google.com'
    assert results[0]['EntryContext']['Email']['To'] == 'test@test.com, example1@example.com'
    assert results[0]['EntryContext']['Email']['CC'] == 'test@test.com, example1@example.com'
    assert results[0]['EntryContext']['Email']['HeadersMap']['From'] == u'"✅✅✅ ВА ! ' \
                                                                        u'https://example.com  ." ' \
                                                                        u'<no-reply@google.com>'
    assert results[0]['EntryContext']['Email']['HeadersMap']['To'] == 'Guy Test <test@test.com>' \
                                                                      ', Guy Test1 <example1@example.com>'
    assert results[0]['EntryContext']['Email']['HeadersMap']['CC'] == 'Guy Test <test@test.com>, ' \
                                                                      'Guy Test1 <example1@example.com>'


def test_email_from_one_line_no_comma_lf(mocker):
    """
    Given:
     - The email message with a 'From' header that contains a newline.
     - Checking an email file that contains '\r\n' in it's 'From' header.

    When:
     - After parsed email file into Email object

    Then:
     - Validate that all raw headers are valid.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '3'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('from_one_line_no_comma_LF'
                                                                                     '.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['From'] == '1111@test.org'
    assert results[0]['EntryContext']['Email']['HeadersMap']['From'] == '\"First Last\" <1111@test.org>'


def test_email_from_newline_lf(mocker):
    """
    Given:
     - The email message with a 'From' header that contains a newline.
     - Checking an email file that contains '\r\n' in it's 'From' header.

    When:
     - After parsed email file into Email object

    Then:
     - Validate that all raw headers are valid.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '3'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('from_multiple_lines_LF'
                                                                                     '.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['From'] == '1111@test.org'


def test_email_from_newline_crlf(mocker):
    """
    Given:
     - The email message with a 'From' header that contains a newline.
     - Checking an email file that contains '\r\n' in it's 'From' header.

    When:
     - After parsed email file into Email object

    Then:
     - Validate that all raw headers are valid.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '3'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('from_multiple_lines_CRLF'
                                                                                     '.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['From'] == '1111@test.org'


def test_email_from_one_line_lf(mocker):
    """
    Given:
     - The email message with a 'From' header that contains a newline.
     - Checking an email file that contains '\r\n' in it's 'From' header.

    When:
     - After parsed email file into Email object

    Then:
     - Validate that all raw headers are valid.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '3'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('from_one_line_LF'
                                                                                     '.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['From'] == '1111@test.org'


def test_email_from_one_line_crlf(mocker):
    """
    Given:
     - The email message with a 'From' header that contains a newline.
     - Checking an email file that contains '\r\n' in it's 'From' header.

    When:
     - After parsed email file into Email object

    Then:
     - Validate that all raw headers are valid.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '3'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('from_one_line_CRLF'
                                                                                     '.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['From'] == '1111@test.org'


def test_eml_contains_eml_with_status(mocker):
    subject = '=?iso-8859-7?B?Rlc6IEZPT0RMSU5LINDLx9HZzMc=?='  # disable-secrets-detection
    decoded = convert_to_unicode(subject)
    subject_attach = decoded.decode('utf-8')
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('ParseEmailFiles-test-emls.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    # assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email'][1]['Subject'] == subject_attach


@pytest.mark.parametrize('email_file', ['eml_contains_base64_eml.eml', 'eml_contains_base64_eml2.eml'])
def test_eml_contains_base64_encoded_eml(mocker, email_file):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file(email_file))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'

    main()
    assert demisto.results.call_count == 3
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email'][0]['Subject'] == 'Fwd: test - inner attachment eml (base64)'
    assert 'message.eml' in results[0]['EntryContext']['Email'][0]['Attachments']
    assert 'message.eml' in results[0]['EntryContext']['Email'][0]['AttachmentsData'][0]['Name']
    assert results[0]['EntryContext']['Email'][0]['Depth'] == 0

    assert results[0]['EntryContext']['Email'][1]["Subject"] == 'test - inner attachment eml'
    assert results[0]['EntryContext']['Email'][1]['Depth'] == 1


# check that we parse an email with "data" type and eml extension
@pytest.mark.parametrize('file_info', ['data', 'data\n'])
def test_eml_data_type(mocker, file_info):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('smtp_email_type.eml', info=file_info))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Test Smtp Email'


def test_smime(mocker):
    multipart_sigened = 'multipart/signed; protocol="application/pkcs7-signature";, ASCII text, with CRLF line terminators'
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('smime.p7m', info=multipart_sigened))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    # assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Testing Email Attachment'


def test_smime_msg(mocker):
    info = 'CDFV2 Microsoft Outlook Message'
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('smime-p7s.msg', info=info))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    # assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'test'


def test_msg_headers_map():
    email_data, ignore = handle_msg('test_data/utf_subject.msg', 'utf_subject.msg')
    assert '?utf-8' not in email_data['Subject']
    assert 'TESTING' in email_data['Subject']
    assert 'This is a test email.' in email_data['Text']
    assert 'mobi777@gmail.com' in email_data['From']
    assert 47 == len(email_data['HeadersMap'])
    assert isinstance(email_data['HeadersMap']['Received'], list)
    assert 8 == len(email_data['HeadersMap']['Received'])
    assert '1; DM6PR11MB2810; 31:tCNnPn/K8BROQtLwu3Qs1Fz2TjDW+b7RiyfdRvmvCG+dGRQ08+3CN4i8QpLn2o4' \
           in email_data['HeadersMap']['X-Microsoft-Exchange-Diagnostics'][2]
    assert '2eWTrUmQCI=; 20:7yMOvCHfrNUNaJIus4SbwkpcSids8EscckQZzX/oGEwux6FJcH42uCQd9tNH8gmDkvPw' \
           in email_data['HeadersMap']['X-Microsoft-Exchange-Diagnostics'][2]
    assert 'text/plain' in email_data['Format']


def test_parse_body_with_russian_language():
    email_data, ignore = handle_msg('test_data/Phishing_TEST.msg', 'Phishing_TEST.msg')
    assert str(email_data['Text']).startswith('\xd0\xa3')
    assert str(email_data['HTML']).startswith('\xd0\xa3')


def test_unknown_file_type(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('smtp_email_type.eml', info="bad"))
    mocker.patch.object(demisto, 'results')
    try:
        main()
    except SystemExit:
        gotexception = True
    assert gotexception
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert 'Unknown file format:' in results[0]['Contents']
    assert 'smtp_email_type.eml' in results[0]['Contents']


def test_no_content_type_file(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('no_content_type.eml', info="ascii text"))
    mocker.patch.object(demisto, 'results')
    main()
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'No content type'


def test_get_msg_mail_format():
    msg_mail_format = get_msg_mail_format({
        'Headers': 'Content-type:text/plain;'
    })
    assert msg_mail_format == 'text/plain'

    msg_mail_format = get_msg_mail_format({
        'Something': 'else'
    })
    assert msg_mail_format == ''

    msg_mail_format = get_msg_mail_format({
        'Headers': None
    })
    assert msg_mail_format == ''


def test_handle_msg_with_attachments():
    """
    Given:
     - A msg file with attachments

    When:
     - Running the 'handle_msg' method

    Then:
     - Ensure that the attachment name is in the results
    """
    result = handle_msg('test_data/html_attachment.msg', 'html_attachment.msg')
    assert result[0]['Attachments'] == 'dummy-attachment.txt'


def test_no_content_file(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('no_content.eml', info="ascii text"))
    mocker.patch.object(demisto, 'results')
    try:
        main()
    except SystemExit:
        gotexception = True
    assert gotexception
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert 'Could not extract email from file' in results[0]['Contents']


def test_eml_contains_htm_attachment(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('eml_contains_htm_attachment.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()

    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email'][u'Attachments'] == '1.htm'
    assert results[0]['EntryContext']['Email'][u'AttachmentsData'][0]['Name'] == '1.htm'


def test_signed_attachment(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('email_with_signed_attachment.eml',
                                                          info="multipart/mixed"))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    results = demisto.results.call_args[0]

    assert len(results[0]['EntryContext']['Email']) == 2


def test_eml_contains_html_and_text(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('multipart_alternative_format.p7m',
                                                          info="multipart/alternative;, "
                                                               "ISO-8859 text, with CRLF line terminators"))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()

    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert "<p class=\"MsoNormal\"><span style='font-size:10.0pt;font-family:" \
           "\"xxxxx\",sans-serif;color:black'>żółć<o:p></o:p>" in results[0]['EntryContext']['Email']['HTML']


def test_eml_format_multipart_mix(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('multipart_mixed_format.p7m',
                                                          info="multipart/mixed"))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()

    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert "Warsaw, Poland <o:p></o:p>" in results[0]['EntryContext']['Email']['HTML']


def test_eml_format_multipart_related(mocker):
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('multipart_related_format.p7m',
                                                          info="multipart/related"))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()

    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert "Warsaw, Poland <o:p></o:p>" in results[0]['EntryContext']['Email']['HTML']


def test_eml_base64_header_comment_although_string(mocker):
    def executeCommand(name, args=None):
        if name == 'getFilePath':
            return [
                {
                    'Type': entryTypes['note'],
                    'Contents': {
                        'path': 'test_data/DONT_OPEN-MALICIOUS_base64_headers.eml',
                        'name': 'DONT_OPEN-MALICIOUS_base64_headers.eml'
                    }
                }
            ]
        elif name == 'getEntry':
            return [
                {
                    'Type': entryTypes['file'],
                    'FileMetadata': {
                        'info': 'UTF-8 Unicode text, with very long lines, with CRLF line terminators'
                    }
                }
            ]
        else:
            raise ValueError('Unimplemented command called: {}'.format(name))

    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=executeCommand)
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    assert demisto.results.call_count == 3
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email'][0]['Subject'] == 'DONT OPEN - MALICIOS'
    assert results[0]['EntryContext']['Email'][0]['Depth'] == 0

    assert 'Attacker+email+.msg' in results[0]['EntryContext']['Email'][0]['Attachments']
    assert 'Attacker+email+.msg' in results[0]['EntryContext']['Email'][0]['AttachmentsData'][0]['Name']
    assert results[0]['EntryContext']['Email'][1]["Subject"] == 'Attacker email'
    assert results[0]['EntryContext']['Email'][1]['Depth'] == 1


def test_message_rfc822_without_info(mocker):
    """
    Given:
     - EML file with content type message/rfc822
     - Demisto entry metadata returned without info, but with type

    When:
     - Running the script on the email file

    Then:
     - Verify the script runs successfully
     - Ensure 2 entries are returned as expected
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': '1'})
    mocker.patch.object(
        demisto,
        'executeCommand',
        side_effect=exec_command_for_file('eml_contains_base64_eml2.eml', info='', file_type='message/rfc822')
    )
    mocker.patch.object(demisto, 'results')
    main()
    assert demisto.results.call_count == 2
    results = demisto.results.call_args_list
    assert len(results) == 2
    assert results[0][0][0]['Type'] == entryTypes['file']
    assert results[1][0][0]['Type'] == entryTypes['note']
    assert results[1][0][0]['EntryContext']['Email']['From'] == 'koko@demisto.com'


def test_md_output_empty_body_text():
    """
    Given:
     - The input email_data where the value of the 'Text' field is None.

    When:
     - Running the data_to_md command on this email_data.

    Then:
     - Validate that output the md doesn't contain a row for the 'Text' field.
    """
    email_data = {
        'To': 'email1@paloaltonetworks.com',
        'From': 'email2@paloaltonetworks.com',
        'Text': None
    }
    expected = u'### Results:\n' \
               u'* From:\temail2@paloaltonetworks.com\n' \
               u'* To:\temail1@paloaltonetworks.com\n' \
               u'* CC:\t\n' \
               u'* Subject:\t\n' \
               u'* Attachments:\t\n\n\n' \
               u'### HeadersMap\n' \
               u'**No entries.**\n'

    md = data_to_md(email_data)
    assert expected == md

    email_data = {
        'To': 'email1@paloaltonetworks.com',
        'From': 'email2@paloaltonetworks.com',
    }
    expected = u'### Results:\n' \
               u'* From:\temail2@paloaltonetworks.com\n' \
               u'* To:\temail1@paloaltonetworks.com\n' \
               u'* CC:\t\n' \
               u'* Subject:\t\n' \
               u'* Attachments:\t\n\n\n' \
               u'### HeadersMap\n' \
               u'**No entries.**\n'

    md = data_to_md(email_data)
    assert expected == md


def test_md_output_with_body_text():
    """
    Given:
     - The input email_data with a value in the 'Text' field.

    When:
     - Running the data_to_md command on this email_data.

    Then:
     - Validate that the output md contains a row for the 'Text' field.
    """
    email_data = {
        'To': 'email1@paloaltonetworks.com',
        'From': 'email2@paloaltonetworks.com',
        'Text': '<email text>'
    }
    expected = u'### Results:\n' \
               u'* From:\temail2@paloaltonetworks.com\n' \
               u'* To:\temail1@paloaltonetworks.com\n' \
               u'* CC:\t\n' \
               u'* Subject:\t\n' \
               u'* Body/Text:\t[email text]\n' \
               u'* Attachments:\t\n\n\n' \
               u'### HeadersMap\n' \
               u'**No entries.**\n'

    md = data_to_md(email_data)
    assert expected == md


def test_create_headers_map_empty_headers():
    """
    Given:
     - The input headers is None.

    When:
     - Running the create_headers_map command on these  headers.

    Then:
     - Validate that the function does not fail
    """
    msg_dict = {
        'From': None, 'CC': None, 'BCC': None, 'To': u'test@demisto.com', 'Depth': 0, 'HeadersMap': {},
        'Attachments': u'image002.png,image003.png,image004.png,image001.png', 'Headers': None, 'Text': u'Hi',
        'Subject': u'test'
    }
    headers, headers_map = create_headers_map(msg_dict.get('Headers'))
    assert headers == []
    assert headers_map == {}


def test_eml_contains_htm_attachment_empty_file(mocker):
    """
    Given: An email containing both an empty text file and a base64 encoded htm file.
    When: Parsing a valid email file with default parameters.
    Then: Three entries will be returned to the war room. One containing the command results. Another
          containing the empty file. The last contains the htm file.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('eml_contains_emptytxt_htm_file.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()

    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email'][0]['AttachmentNames'] == ['unknown_file_name0', 'SomeTest.HTM']


def test_eml_contains_attachment_with_unknown_encoded_file_name(mocker):
    """
    Given: An email containing an attachment with unknown encoded name.
    When: Parsing a valid email file with default parameters.
    Then: The file name is parsed as expected and the debug alert exist.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('Unknown_encode_attachment_name.eml'))
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(demisto, 'debug')

    main()
    results = demisto.results.call_args[0]
    debug = demisto.debug.call_args[0]

    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['AttachmentNames'] == ['04AIf|???���������������.pdf']
    assert debug[0] == 'Could not find the encoding type of the string, decoding by default with utf-8'


def test_eml_contains_htm_attachment_empty_file_max_depth(mocker):
    """
    Given: An email containing both an empty text file and a base64 encoded htm file.
    When: Parsing a valid email file with max_depth=1.
    Then: One entry containing the command results will be returned to the war room.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test', 'max_depth': 1})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('eml_contains_emptytxt_htm_file.eml'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()

    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']


def test_double_dots_removed(mocker):
    """
    Fixes: https://github.com/demisto/etc/issues/27229
    Given:
        an eml file with a line break (`=\r\n`) which caused the duplication of dots (`..`).
    Then:
        replace the two dots with one and test that `part.get_payload()` decodes it correctly.
    """
    import ParseEmailFiles as pef
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('multiple_to_cc.eml'))
    mocker.patch.object(pef, 'get_utf_string')
    main()
    assert 'http://schemas.microsoft.com/office/2004/12/omml' in pef.get_utf_string.mock_calls[0][1][0]


def test_only_parts_of_object_email_saved(mocker):
    """

    Fixes: https://github.com/demisto/etc/issues/29476
    Given:
        an eml file with a line break (`\n`) in the payload that has failed due to wring type.
    Then:
        filter only parts that are of type email.message.Message.

    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('new-line-in-parts.eml'))
    mocker.patch.object(demisto, 'results')

    main()

    results = demisto.results.call_args[0]

    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['AttachmentNames'] == ['logo5.png', 'logo2.png']


def test_long_subject_and_special_characters(mocker):
    """

    Fixes: https://github.com/demisto/etc/issues/47691
    Given:
        an eml file with a long subject and special characters.
    Then:
        assert all the subject is parsed correctly.

    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})
    mocker.patch.object(demisto, 'executeCommand', side_effect=exec_command_for_file('Those_characters___'
                                                                                     '_will_mess_with_'
                                                                                     'the_parsing_automation.eml'))
    mocker.patch.object(demisto, 'results')

    main()

    results = demisto.results.call_args[0]

    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == u'Those characters : üàéüö will mess with the ' \
                                                             u'parsing automation'


def test_pkcs7_mime(mocker):
    """
    Given: An email file smime2.p7m of type application/pkcs7-mime and info -
    MIME entity text, ISO-8859 text, with very long lines, with CRLF line terminators
    When: Parsing the email.
    Then: The email is parsed correctly.
    """
    mocker.patch.object(demisto, 'args', return_value={'entryid': 'test'})

    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=exec_command_for_file('smime2.p7m',
                                                          info='MIME entity text, ISO-8859 text, with very long lines,'
                                                               ' with CRLF line terminators'))
    mocker.patch.object(demisto, 'results')
    # validate our mocks are good
    assert demisto.args()['entryid'] == 'test'
    main()
    assert demisto.results.call_count == 1
    # call_args is tuple (args list, kwargs). we only need the first one
    results = demisto.results.call_args[0]
    assert len(results) == 1
    assert results[0]['Type'] == entryTypes['note']
    assert results[0]['EntryContext']['Email']['Subject'] == 'Testing signed multipart email'


def test_PtypString():
    data_value = DataModel.PtypString('IPM.Note')
    assert data_value == u'IPM.Note'

    data_value = DataModel.PtypString('I\x00P\x00M\x00.\x00N\x00o\x00t\x00e\x00')
    assert data_value == u'IPM.Note'

    data_value = DataModel.PtypString(b'e\x9c\xe6\xb9pe')
    assert data_value == u'eśćąpe'


@pytest.mark.parametrize('payload, answer', [
    ('escape', 'escape'),
    (u'eśćąpe', u'eśćąpe')
])
def test_decode_attachment_payload_non_base64(payload, answer):
    class MockedMessage:
        def __init__(self, payload=None):
            self.payload = payload

        def get_payload(self):
            return self.payload

    from ParseEmailFiles import decode_attachment_payload
    assert answer == decode_attachment_payload(MockedMessage(payload))


@pytest.mark.parametrize('payload, answer', [
    ('//5lAFsBBwEFAXAAZQA=', '\xff\xfee\x00[\x01\x07\x01\x05\x01p\x00e\x00'),  # eśćąpe
    ('ZXNjYXBl', 'escape')
])
def test_decode_attachment_payload_base64(payload, answer):
    class MockedMessage:
        def __init__(self, payload=None):
            self.payload = payload

        def get_payload(self):
            return self.payload

    from ParseEmailFiles import decode_attachment_payload
    assert answer == decode_attachment_payload(MockedMessage(payload))


@pytest.mark.parametrize('nesting_level_to_return, output, res', [('All files', ['output1'], ('output1', ['output1'])),
                                                                  ('Outer file', ['output1', 'output2', 'output3'],
                                                                   ('output1', 'output1')),
                                                                  ('Inner file', ['output1', 'output2', 'output3'],
                                                                   ('output3', 'output3'))])
def test_parse_nesting_level(nesting_level_to_return, output, res):
    """
    Given:
    - parsed email output, nesting_level_to_return param - All files.
    - parsed email output, nesting_level_to_return param - Outer file.
    - parsed email output, nesting_level_to_return param - Inner file.
    When:
    - Getting all nested emails.
    - Getting only outer email file.
    - Getting only inner email file.
    Then: Validate that returned result as expected.
    """
    assert parse_nesting_level(nesting_level_to_return, output) == res
