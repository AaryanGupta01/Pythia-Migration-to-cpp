def encrypt(text, shift):
    result = ""
    for ch in text:
        if ch.isalpha():
            base = ord('A') if ch.isupper() else ord('a')
            result += chr((ord(ch) - base + shift) % 26 + base)
        else:
            result += ch
    return result


def decrypt(text, shift):
    return encrypt(text, -shift)


message = input("Message: ")
shift = int(input("Shift: "))
secret = encrypt(message, shift)
print("Encrypted:", secret)
print("Decrypted:", decrypt(secret, shift))
