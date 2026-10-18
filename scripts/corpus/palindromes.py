def is_palindrome(s):
    cleaned = "".join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]


words = ["racecar", "A man, a plan, a canal: Panama", "hello", "Was it a car or a cat I saw?", "python"]
for w in words:
    print(f"{w!r}: {'palindrome' if is_palindrome(w) else 'not a palindrome'}")

count = sum(1 for w in words if is_palindrome(w))
print(f"{count} of {len(words)} are palindromes")
