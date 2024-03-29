"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""
import builtins
import google.protobuf.descriptor
import google.protobuf.internal.enum_type_wrapper
import google.protobuf.message
import typing
import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor = ...

class Ting(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
    class Packet(metaclass=_Packet):
        V = typing.NewType('V', builtins.int)

    CLOSE = Ting.Packet.V(0)
    TING = Ting.Packet.V(1)

    class _Packet(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[Packet.V], builtins.type):
        DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor = ...
        CLOSE = Ting.Packet.V(0)
        TING = Ting.Packet.V(1)

    TIME_SEC_FIELD_NUMBER: builtins.int
    PTYPE_FIELD_NUMBER: builtins.int
    time_sec: builtins.float = ...
    ptype: global___Ting.Packet.V = ...

    def __init__(self,
        *,
        time_sec : typing.Optional[builtins.float] = ...,
        ptype : typing.Optional[global___Ting.Packet.V] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal[u"ptype",b"ptype",u"time_sec",b"time_sec"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal[u"ptype",b"ptype",u"time_sec",b"time_sec"]) -> None: ...
global___Ting = Ting
