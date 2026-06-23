

def hello():
    print("hello")
    yield
    print("world")


if __name__ == "__main__":
    for i in hello():
        print(i)