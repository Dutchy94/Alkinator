import snap7
from snap7.type import Area, WordLen
import struct

class UDTFlasche:
    def __init__(self, name='Keiner', x=0.0, y=0.0, dosier_art=False, dosiermenge=20, alkoholgehalt=0.0):
        self.name = name  # String[20]
        self.x = x  # Real (4 Bytes)
        self.y = y  # Real (4 Bytes)
        self.dosier_art = dosier_art  # Bool (1 Bit)
        self.dosiermenge = dosiermenge  # UInt (2 Bytes)
        self.alkoholgehalt = alkoholgehalt  # Real (4 Bytes)


    def to_bytes(self):
        """Packt die Flaschendaten in ein Byte-Array für die SPS."""
        max_length = 20
        actual_length = min(len(self.name), max_length)

        # Name (STRING[20] mit maximaler und aktueller Länge)
        name_encoded = struct.pack(
            f'>BB{max_length}s', 
            max_length, 
            actual_length, 
            self.name.ljust(max_length).encode('ascii')
        )

        # Dosierart als Byte (0 oder 1)
        dosier_art_byte = 1 if self.dosier_art else 0

        # Packen der restlichen Felder
        return name_encoded + struct.pack(
            '>ffB xHf',  # x = Padding nach BOOL
            self.x,                # REAL
            self.y,                # REAL
            dosier_art_byte,       # BOOL (1 Byte)
            self.dosiermenge,      # UINT (2 Bytes)
            self.alkoholgehalt     # REAL (4 Bytes)
        )

    @classmethod
    def from_bytes(cls, data):
        """Entpackt die Flaschendaten aus einem Byte-Array."""
        try:
            if len(data) < 38:
                raise ValueError(f"Ungültige Datenlänge: Erwartet 38 Bytes, erhalten {len(data)} Bytes")
            
            print(f"Empfangene Rohdaten (Hex): {data.hex()}")
            
            # Name
            max_length, actual_length, name_raw = struct.unpack('>BB20s', data[:22])
            if max_length != 20:
                raise ValueError(f"Ungültige maximale Länge für den Namen: {max_length}, erwartet 20")
            
            name = name_raw[:actual_length].decode('ascii', errors='ignore').strip()
            print(f"Name: {name} (Max: {max_length}, Aktuell: {actual_length})")

            # Restliche Daten
            x, y = struct.unpack('>ff', data[22:30])
            print(f"X: {x}, Y: {y}")

            dosier_art_byte, = struct.unpack('>B', data[30:31])
            dosier_art = bool(dosier_art_byte)
            print(f"DosierArt: {'Hub' if dosier_art else 'Zeit'}")

            dosiermenge, = struct.unpack('>H', data[32:34])
            print(f"Dosiermenge: {dosiermenge}")

            alkoholgehalt, = struct.unpack('>f', data[34:38])
            print(f"Alkoholgehalt: {alkoholgehalt}")

            # Rückgabe eines neuen Objekts der Klasse
            return cls(
                name=name,
                x=x,
                y=y,
                dosier_art=dosier_art,
                dosiermenge=dosiermenge,
                alkoholgehalt=alkoholgehalt
            )
        except UnicodeDecodeError as e:
            print(f"Fehler beim Dekodieren des Namens: {e}")
            raise ValueError("Ungültige Zeichen im Namen gefunden") from e
        except struct.error as e:
            print(f"Fehler beim Parsen der Struktur: {e}")
            raise ValueError("Die Daten konnten nicht korrekt entpackt werden") from e
        except Exception as e:
            print(f"Unbekannter Fehler beim Parsen der Bytes: {e}")
            raise

def __str__(self):
    """Gibt die Flaschendaten als lesbaren String zurück."""
    try:
        dosier_art_str = 'Hub' if self.dosier_art else 'Zeit'
        return (
            f"Name: {self.name}, X: {self.x:.2f}, Y: {self.y:.2f}, "
            f"DosierArt: {dosier_art_str}, Dosiermenge: {self.dosiermenge} ml, "
            f"Alkoholgehalt: {self.alkoholgehalt:.2f}%"
        )
    except AttributeError as e:
        return f"Fehler bei der Darstellung der Flaschendaten: {e}"

    
class SPSKommunikation:
    # Verbindung zur SPS
    def __init__(self, ip, rack=0, slot=0):
        self.client = snap7.client.Client()
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self.connect()

    def connect(self):
        try:
            self.client.connect(self.ip, self.rack, self.slot)
            print(f"Erfolgreich mit SPS {self.ip} verbunden.")
        except Exception as e:
            print(f"Fehler beim Verbinden zur SPS: {e}")
            raise e

    def disconnect(self):
        self.client.disconnect()
        print("Verbindung zur SPS getrennt.")

    def read_db(self, db_number, start, size):
        """Liest Rohdaten aus einem Datenbaustein."""
        return self.client.read_area(Area.DB, db_number, start, size)

    def write_db(self, db_number, start, data):
        """Schreibt Rohdaten in einen Datenbaustein."""
        self.client.write_area(Area.DB, db_number, start, data)

    def read_flasche(self, db_number, index, udt_size=38):
        """
        Liest eine spezifische Flasche aus dem Array.
        :param db_number: Nummer des Datenbausteins
        :param index: Index der Flasche (1-basiert)
        :param udt_size: Größe eines UDTs
        :return: UDTFlasche-Objekt
        """
        if index < 1 or index > 30:
            raise ValueError("Index muss zwischen 1 und 30 liegen.")
        start_address = (index - 1) * udt_size
        raw_data = sps.read_db(db_number, array_start, total_size)
        print(f"DB: {db_number}, Start: {array_start}, Größe: {total_size}")
        print(f"Rohdaten: {raw_data.hex()}")
        return UDTFlasche.from_bytes(raw_data)

    def write_flasche(self, db_number, index, flasche, udt_size=38):
        """
        Schreibt eine spezifische Flasche in das Array.
        :param db_number: Nummer des Datenbausteins
        :param index: Index der Flasche (1-basiert)
        :param flasche: UDTFlasche-Objekt
        :param udt_size: Größe eines UDTs
        """
        if index < 1 or index > 30:
            raise ValueError("Index muss zwischen 1 und 30 liegen.")
        start_address = (index - 1) * udt_size

        data_to_write = flasche.to_bytes()
        print(f"Flasche {index} Daten vor dem Schreiben (Hex): {data_to_write.hex()}")

        self.write_db(db_number, start_address, data_to_write)
        print(f"Flasche {index} erfolgreich in SPS geschrieben.")

    def set_bit(self, db_number, byte_index, bit_index, value):
        """
        Setzt ein spezifisches Bit in einer Datenbank.
        :param db_number: Nummer der DB
        :param byte_index: Offset des Bytes
        :param bit_index: Index des Bits im Byte (0-7)
        :param value: True für 1, False für 0
        """
        try:
            # Lese das aktuelle Byte
            current_byte = self.client.db_read(db_number, byte_index, 1)[0]
            print(f"Aktuelles Byte: {current_byte:08b}")

            # Bitmaske erstellen
            mask = 1 << bit_index

            # Setze oder lösche das Bit
            if value:
                new_byte = current_byte | mask  # Bit setzen
            else:
                new_byte = current_byte & ~mask  # Bit löschen

            print(f"Neues Byte: {new_byte:08b}")

            # Schreibe das Byte zurück
            self.client.db_write(db_number, byte_index, bytes([new_byte]))
        except Exception as e:
            print(f"Fehler beim Setzen des Bits: {e}")
            raise

def read_udt_array(sps, db_number, array_start, udt_size, array_length):
    total_size = udt_size * array_length
    raw_data = sps.read_db(db_number, array_start, total_size)
    print(f"Rohdaten aus der SPS (Hex): {raw_data.hex()}")
    print(f"Erwartete Größe: {total_size}, Tatsächliche Größe: {len(raw_data)}")
    
    if len(raw_data) < total_size:
        raise ValueError(f"Nicht genug Daten: Erwartet {total_size} Bytes, erhalten {len(raw_data)} Bytes")

    udt_list = []
    for i in range(array_length):
        start = i * udt_size
        end = start + udt_size
        udt_data = raw_data[start:end]
        print(f"Flasche {i+1} Daten: {udt_data.hex()} (Länge: {len(udt_data)})")
        
        if len(udt_data) != udt_size:
            raise ValueError(f"Flasche {i+1} hat die falsche Größe: {len(udt_data)} Bytes, erwartet {udt_size}")
        
        udt = UDTFlasche.from_bytes(udt_data)
        udt_list.append(udt)

    return udt_list