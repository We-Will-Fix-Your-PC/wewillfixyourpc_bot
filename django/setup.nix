{ pkgs ? import <nixpkgs> {}
, pythonPackages ? pkgs.python37Packages
, setup ? import (fetchTarball {
    url = "https://github.com/datakurre/setup.nix/archive/v3.0.tar.gz";
    sha256 = "0s3drfcbyp21v8qvlwrpabldsc2aqqpic9r8dmnayqgjixcb09mc";
  })
}:

setup {
  inherit pkgs pythonPackages;
  src = ./.;
  overrides = self: super: {
    "cffi" = super."cffi".override (attrs: {
      propagatedBuildInputs = attrs.propagatedBuildInputs ++ [
        pkgs.libffi
      ];
    });

    "cryptography" = super."cryptography".override (attrs: {
      buildInputs = attrs.buildInputs ++ [
         pkgs.openssl
      ];
    });
    "Pillow" = super.Pillow.override (attrs: {
        postPatch = ''
          rm Tests/test_imagefont.py
        '';

        buildInputs = with pkgs; [
          freetype libjpeg zlib libtiff libwebp tcl lcms2 ];

        # NOTE: we use LCMS_ROOT as WEBP root since there is not other setting for webp.
        preConfigure = let
          libinclude' = pkg: ''"${pkg.out}/lib", "${pkg.out}/include"'';
          libinclude = pkg: ''"${pkg.out}/lib", "${pkg.dev}/include"'';
        in with pkgs; ''
          sed -i "setup.py" \
              -e 's|^FREETYPE_ROOT =.*$|FREETYPE_ROOT = ${libinclude freetype}|g ;
                  s|^JPEG_ROOT =.*$|JPEG_ROOT = ${libinclude libjpeg}|g ;
                  s|^ZLIB_ROOT =.*$|ZLIB_ROOT = ${libinclude zlib}|g ;
                  s|^LCMS_ROOT =.*$|LCMS_ROOT = ${libinclude lcms2}|g ;
                  s|^TIFF_ROOT =.*$|TIFF_ROOT = ${libinclude libtiff}|g ;
                  s|^TCL_ROOT=.*$|TCL_ROOT = ${libinclude' tcl}|g ;'
          export LDFLAGS="-L${libwebp}/lib"
          export CFLAGS="-I${libwebp}/include"
        '';
      });
    "psycopg2-binary" = super."psycopg2-binary".override (attrs: {
      nativeBuildInputs = attrs.nativeBuildInputs ++ [
        pkgs.postgresql
      ];
    });
    "python-magic" = pythonPackages.python_magic;
    "twisted" = pythonPackages.twisted;
    "six" = pythonPackages.six;
    "zope.interface" = pythonPackages.zope_interface;
    "zope.event" = pythonPackages.zope_event;
    "incremental" = pythonPackages.incremental;
    "Automat" = pythonPackages.automat;
    "attrs" = pythonPackages.attrs;
    "constantly" = pythonPackages.constantly;
    "hyperlink" = pythonPackages.hyperlink;
    "idna" = pythonPackages.idna;
    "mastercard-oauth1-signer" = super."mastercard-oauth1-signer".override(attrs: {
      postInstall = ''
        rm -r $out/${pkgs.python37.sitePackages}/tests/
      '';
    });
  };
}
