// testbenches/arithmetic/adder_known_broken.sv
// Intentionally broken: sum width too narrow, silently drops carry out.
// Used ONLY to prove the harness correctly detects a functional mismatch.
module adder #(parameter WIDTH = 8) (
    input  logic [WIDTH-1:0] a,
    input  logic [WIDTH-1:0] b,
    output logic [WIDTH:0]   sum
);
    logic [WIDTH-1:0] narrow_sum;
    assign narrow_sum = a + b;      // BUG: drops carry-out bit
    assign sum = {1'b0, narrow_sum}; // always reports carry=0, wrong for overflow cases
endmodule
