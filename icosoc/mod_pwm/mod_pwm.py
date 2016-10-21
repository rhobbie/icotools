
def generate_c_code(icosoc_h, icosoc_c, mod):
    code = """
static inline void icosoc_@name@_setcounter(uint32_t val)
{
    *(uint32_t*)(0x20000000 + @addr@ * 0x10000) = val;
}

static inline void icosoc_@name@_setmaxcnt(uint32_t val)
{
    *(uint32_t*)(0x20000004 + @addr@ * 0x10000) = val;
}

static inline void icosoc_@name@_setoncnt(uint32_t val)
{
    *(uint32_t*)(0x20000008 + @addr@ * 0x10000) = val;
}

static inline void icosoc_@name@_setoffcnt(uint32_t val)
{
    *(uint32_t*)(0x2000000c + @addr@ * 0x10000) = val;
}

static inline uint32_t icosoc_@name@_getcounter()
{
    return *(uint32_t*)(0x20000000 + @addr@ * 0x10000);
}

static inline uint32_t icosoc_@name@_getmaxcnt()
{
    return *(uint32_t*)(0x20000004 + @addr@ * 0x10000);
}

static inline uint32_t icosoc_@name@_getoncnt()
{
    return *(uint32_t*)(0x20000008 + @addr@ * 0x10000);
}

static inline uint32_t icosoc_@name@_getoffcnt()
{
    return *(uint32_t*)(0x2000000c + @addr@ * 0x10000);
}
"""
    code = code.replace("@name@", mod["name"])
    code = code.replace("@addr@", mod["addr"])
    icosoc_h.append(code)
