#!/usr/bin/env python

import requests
import binascii
import javaobj
import StringIO
import struct
import sys
import getpass
import argparse
import logging # To make javaobj's logger be quiet
from read_minimed_next24 import Config

class CareLinkRequest( javaobj.JavaObjectMarshaller ):
    def __init__( self ):
        self.object_stream = StringIO.StringIO()
        self._writeStreamHeader()

class CareLinkKeyRequest( CareLinkRequest ):
    def buildRequest( self, serial ):
        self.writeObject( struct.pack( '>I', 0x1f ) )
        self.write_string( serial )
        return self.object_stream.getvalue()

    def decodeResponse( self, data ):
        decoder = javaobj.JavaObjectUnmarshaller( StringIO.StringIO( data ) )
        int1 = struct.unpack( '>I', decoder.readObject() )[0]
        keyArray = decoder.readObject()
        key = ''.join('{:02x}'.format( x & 0xff ) for x in keyArray )
        count = struct.unpack( '>I', decoder.readObject() )[0]
        return ( int1, key, count )

class CareLinkHMACRequest( CareLinkRequest ):
    def buildRequest( self, serial ):
        self.writeObject( struct.pack( '>I', 0x1c ) )
        self.write_string( serial )
        return self.object_stream.getvalue()

    def decodeResponse( self, data ):
        decoder = javaobj.JavaObjectUnmarshaller( StringIO.StringIO( data ) )
        hmacArray = decoder.readObject()
        hmac = ''.join('{:02x}'.format( x & 0xff ) for x in reversed(hmacArray) )
        return hmac

if __name__ == '__main__':
    logging.disable( logging.CRITICAL )

    parser = argparse.ArgumentParser()
    parser.add_argument( 'username' )
    parser.add_argument( 'serial' )
    args = parser.parse_args()

    # set up the sqlite3 database if required...
    config = Config( args.serial )

    password = getpass.getpass( 'Enter the password for the CareLink user {0}: '.format( args.username ) )

    payload = {
        'j_username': args.username,
        'j_password': password,
        'j_character_encoding': 'UTF-8'
    }

    with requests.Session() as session:
        session.post( 'https://carelink.minimed.eu/patient/j_security_check', data = payload )

        request = CareLinkHMACRequest()
        data = request.buildRequest( args.serial )

        response = session.post( 'https://carelink.minimed.eu/patient/main/../secure/SnapshotServer/',
            headers = { 'Content-Type': 'application/octet-stream' },
            stream = True,
            data = data
        )

        hmac = request.decodeResponse( response.raw.read() )

        request = CareLinkKeyRequest()
        data = request.buildRequest( '6213-{0}'.format( args.serial ) )

        response = session.post( 'https://carelink.minimed.eu/patient/main/../secure/SnapshotServer/',
            headers = { 'Content-Type': 'application/octet-stream' },
            stream = True,
            data = data
        )

        ( int1, key, count ) = request.decodeResponse( response.raw.read() )

        config.hmac = hmac
        config.key = key
        print( 'HMAC: {0}'.format( hmac ) )
        print( 'KEY: {0}'.format( key ) )
