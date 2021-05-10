# Service container

## Introduction

The service container is the place where all application's components are defined. The application component is a variable of any type that resides in the container and can be
retrieved at any time on demand.

### The core principles:

* use python-native type hinting
* function signature must not be changed to support dependency injection
* the container must invoke any callable injecting dependencies
* the developer must be able to pass hints to the injector for more fine-grained injection control

### Limitations

Currently, the service container does not support positional-only function arguments. If you try to invoke a function or method containing positional-only arguments
the `kupala.container.PositionOnlyArgumentError` will be raised.

Also, the container raises `kupala.container.NoTypeHintError` when you try to invoke a callable without typehints.

### Example usage

Following these rules an example usage looks like:

```python
from kupala.container import Container


class Mailer:
    def send_mail(self, to: str, body: str): ...


def send_mail(mailer: Mailer):
    mailer.send_mail('someone@earth.tld', 'Hello world!')


container = Container()
container.bind(Mailer, Mailer())
container.invoke(send_mail)
```

Let's see what happens here.  
First, we define a `Mailer` service. This is an example class that sends email messages.

```python
class Mailer:
    def send_mail(self, to: str, body: str): ...

```

Next, we define a `send_mail` function that depends on `Mailer` instance and does the actual mail sending.

```python
def send_mail(mailer: Mailer):
    mailer.send_mail('someone@earth.tld', 'Hello world!')

```

At this stage nothing special happens, we use plain Python code. To make the magic work, we create an instance of the `Container` class and bind an instance of `Mailer` into it.

```python
container = Container()
container.bind(Mailer, Mailer())
```

Now the container contains an instance of `Mailer` and we can use it to call `send_mail` function. The container will read arguments and their types from the `send_mail`'s
signature and will inject required dependencies.

```python
container.invoke(send_mail)
```

Here the container calls `send_mail` automatically resolving and injecting the `Mailer` service as specified in the function's signature.

Also, you can retrieve any bound service just by calling `container.get(Mailer)`.

## Registering services

There are three service types available: instances, factories and singletons. Each of them has own use case. You can register any variable as a service: integers, strings, classes,
instances, etc. The term "service" basically means something nesting is in the container.

!!! note "Service names"
You can use a class or a string as a service name.

### Instance type

Services of type "instance" are the simplest ones. They are, basically, variables that are bound to the container as is. To register a service use `container.bind` function.

```python
from kupala.container import Container

container = Container()
container.bind('MyService', 'value')

assert container.get('MyService') == 'value'  # true
```

Each time you request the service the bound instance will be returned. You may also bind a service using dict-like interface:

```python
container['MyService'] = 'value'
```

### Factory type

Unlike instance services, factory-based services return a new instance when you retrieve the service. To register such service you need to bind a factory function to the container
using `container.factory` method.

```python
from kupala.container import Container


class User: ...


def user_factory() -> User:
    return User()


container = Container()
container.factory(User, user_factory)

instance1 = container.get(User)
instance2 = container.get(User)

assert instance1 == instance2  # false
```

The factory functions may depend on another services. These services will be properly resolved and injected when the factory function gets called.

```python
from kupala.container import Container


class Transport: ...


class Mailer:
    def __init__(self, transport: Transport): ...


def mailer_factory(transport: Transport) -> Mailer:
    return Mailer(transport)


container = Container()
container.bind(Transport, Transport())
container.factory(Mailer, mailer_factory)

mailer = container.get(Mailer)  # returns instance of Mailer class with transport injected
```

### Singleton type

A singleton service is much like the factory service, but it caches the result of the factory function. This means, the factory function is called only once, each subsequent call
will return the same service instance. Add a singleton service with `container.singleton` method.

```python
from kupala.container import Container


class User: ...


def user_factory() -> User:
    return User()


container = Container()
container.singleton(User, user_factory)

instance1 = container.get(User)
instance2 = container.get(User)

assert instance1 == instance2  # true
```

## Retrieving services

You can retrieve a service from the container by calling `container.get` method. If the service is not registered in the container the `kupala.container.ServiceNotFound` exception
raised.

```python
from kupala.container import Container


class User: ...


container = Container()
container.bind(User, User())

container.get(User)
```

The container class also supports dict-like access to the container's services:

```python
user = container[User]
```

## Aliases

Sometimes you need to provide an alternate name to your services. You can use aliases for this purpose. Use `container.get` method to get a service by alias.

```python
from kupala.container import Container


class Mailer: ...


container = Container()
container.bind(Mailer, Mailer(), aliases='mailer')
# or add multiple aliases at once
container.bind(Mailer, Mailer(), aliases=['mailer', 'default_mailer'])

mailer = container.get('mailer')  # get instance by alias
```

It is also possible to alias a service, that is already in the container.

```python
container.alias('someserviceinthecontainer', 'newservicename')
```

A string alias cannot be used as typehint and therefore cannot be injected into the function. To solve this issue use `kupala.container.service` special type:

```python
from kupala.container import Container, service


def factory(user: service('user')):
    return user


container = Container()
container.bind('user', 'root')

assert container.invoke(factory) == 'root'
```

If the alias already exists in the container a `kupala.container.AliasExistsError` raises.

## Tags

Tags are special attributes assigned to a service that you can use to group related services.

```python
from kupala.container import Container


class FileCache: ...


class MemoryCache: ...


class RedisCache: ...


container = Container()
container.bind('file_cache_driver', FileCache, tags='cache.driver')
container.bind('memory_cache_driver', MemoryCache, tags='cache.driver')
container.bind('redis_cache_driver', RedisCache, tags='cache.driver')

cache_drivers = container.get_by_tag('cache.driver')
# [FileCache, MemoryCache, RedisCache]
```

In the same way as with aliases, you can inject services using tag name into a callable:

```python
from kupala.container import tag


def make_cache(drivers: tag('cache.driver')):
    return drivers


result = container.invoke(make_cache)
# [FileCache, MemoryCache, RedisCache]
```

## Invoking callables

The container can invoke any callable (a function, a class, or a method) injecting dependencies listed in the signature.

```python
from kupala.container import Container


class User: ...


def some_fn(user: User):
    return 'ok'


container = Container()
container.bind(User, User())
result = container.invoke(some_fn)
# result = 'ok'
```

In the example above the container will inspect the signature of `some_fn`, look up for a service named `User` and will call `some_fn` passing found service as the function's
argument. The invocation result will be returned back to you. In other works, this is like if you get a dependency from the container and pass it to the callable by hands:

```python
user = container.get(User)
result = some_fn(user)
# result = 'ok'
```

### Passing extra dependencies (hints)

Sometimes a callable depends on a value that is absent in the container, or you want to override (or add) a service for a current invocation. You can pass any count of keyword
arguments to `invoke` method, and they will be passed to the function being called.

```python
from kupala.container import Container


class UserRepo: ...


def filter_users(repo: UserRepo, is_enabled: bool): ...


container = Container()
container.bind(UserRepo, UserRepo())
container.invoke(filter_users, is_enabled=True)
```

## Removing services

Use `remove` method to remove a service from the container. This will remove aliases and tags as well.

## Hooks

Hooks are special functions that called by the container on some events.

### After service created

You can use `add_post_create_hook` to register a function that will be executed when the factory done creating a service. This is applicable to `factory` and `singleton` service
types.

```python
from kupala.container import Container


class Mailer: ...


def on_service_created(mailer: Mailer):
    print('mailer created')


def mailer_factory():
    return Mailer()


container = Container()
container.factory(Mailer, mailer_factory)
container.add_post_create_hook(Mailer, on_service_created)
container.get(Mailer)
# prints 'mailer created'
```

!!! note 
    The hook is called only once for singleton service type.
