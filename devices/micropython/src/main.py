import thingsboard_ota_links

print("Hola desde main.py")

import thing
if hasattr(thing, "main"):
    main_function = getattr(thing, "main")
    if callable(main_function):
        thing.main()
