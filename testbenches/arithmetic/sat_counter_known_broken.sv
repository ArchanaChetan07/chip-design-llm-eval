// testbenches/arithmetic/sat_counter_known_broken.sv
// Intentionally broken: no saturation check, wraps around at boundaries
// instead of holding at MAX_VAL / 0.
module sat_counter #(
    parameter WIDTH = 4,
    parameter MAX_VAL = (1 << WIDTH) - 1
) (
    input  logic clk, rst_n,
    input  logic up, down,
    output logic [WIDTH-1:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 0;
        end else begin
            if (up && !down) begin
                count <= count + 1;   // BUG: no saturation, wraps at MAX_VAL
            end else if (down && !up) begin
                count <= count - 1;   // BUG: no floor check, wraps at 0
            end
        end
    end
endmodule
