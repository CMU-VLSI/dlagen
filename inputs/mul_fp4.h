#pragma hls_design ccore
p_t mul_fp4(
    ac_int<4, true> a,
    ac_int<4, true> b) {

    ac_int<2, false> a_exp = a.template slc<2>(1);
    ac_int<2, false> b_exp = b.template slc<2>(1);
    ac_int<2, false> a_mant, b_mant;
    bool issubnormal_a = a_exp == 0;
    bool issubnormal_b = b_exp == 0;
    a_mant[1] = !issubnormal_a;
    b_mant[1] = !issubnormal_b;
    a_mant[0] = a[0];
    b_mant[0] = b[0];
    if (!issubnormal_a) {
        a_exp = a_exp - 1;
    } else {
        a_exp = a_exp;
    }
    if (!issubnormal_b) {
        b_exp = b_exp - 1;
    } else {
        b_exp = b_exp;
    }
    // implicit 4x the real output from mant
    ac_int<3, false> c_exp = a_exp + b_exp;
    p_t c = a_mant * b_mant;
    c = c << (c_exp);
    if (a[3] ^ b[3]) {
        c = c * -1;
    } else {
        c = c;
    }
    return c;
}